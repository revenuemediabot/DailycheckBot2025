#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DailyCheck Bot v4.0 - Enhanced AI Service
Интеллектуальный AI-ассистент с продвинутыми возможностями

Автор: AI Assistant
Версия: 4.0.1
Дата: 2025-06-12
"""

import asyncio
import json
import random
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

# Проверяем доступность OpenAI
try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Импорты из нашего проекта
from core.models import User, AIRequestType, TaskCategory, ValidationError
from config import config

logger = logging.getLogger(__name__)

# ===== EXCEPTIONS =====

class AIServiceError(Exception):
    """Базовое исключение для AI сервиса"""
    pass

class AIProviderError(AIServiceError):
    """Ошибка провайдера AI"""
    pass

class AIRateLimitError(AIServiceError):
    """Ошибка превышения лимита запросов"""
    pass

class AIContextError(AIServiceError):
    """Ошибка контекста AI"""
    pass

# ===== ENUMS =====

class AIProvider(Enum):
    """Провайдеры AI"""
    OPENAI = "openai"
    FALLBACK = "fallback"

class PromptTemplate(Enum):
    """Шаблоны промптов"""
    SYSTEM_BASE = "system_base"
    MOTIVATION = "motivation"
    COACHING = "coaching"
    PSYCHOLOGY = "psychology"
    ANALYSIS = "analysis"
    TASK_SUGGESTION = "task_suggestion"
    GENERAL = "general"

class ResponseQuality(Enum):
    """Качество ответа"""
    EXCELLENT = "excellent"
    GOOD = "good"
    ACCEPTABLE = "acceptable"
    POOR = "poor"

# ===== DATA CLASSES =====

@dataclass
class AIRequest:
    """Запрос к AI"""
    user_id: int
    message: str
    request_type: AIRequestType
    context: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'user_id': self.user_id,
            'message': self.message,
            'request_type': self.request_type.value,
            'context': self.context,
            'timestamp': self.timestamp,
            'session_id': self.session_id
        }

@dataclass
class AIResponse:
    """Ответ AI"""
    content: str
    request_type: AIRequestType
    provider: AIProvider
    quality: ResponseQuality = ResponseQuality.GOOD
    tokens_used: int = 0
    response_time_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    cached: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'content': self.content,
            'request_type': self.request_type.value,
            'provider': self.provider.value,
            'quality': self.quality.value,
            'tokens_used': self.tokens_used,
            'response_time_ms': self.response_time_ms,
            'timestamp': self.timestamp,
            'cached': self.cached
        }

@dataclass
class AIStats:
    """Статистика AI сервиса"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    cached_responses: int = 0
    total_tokens_used: int = 0
    average_response_time_ms: float = 0.0
    requests_by_type: Dict[str, int] = field(default_factory=dict)
    provider_usage: Dict[str, int] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def cache_hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.cached_responses / self.total_requests) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'cached_responses': self.cached_responses,
            'total_tokens_used': self.total_tokens_used,
            'average_response_time_ms': round(self.average_response_time_ms, 2),
            'success_rate': round(self.success_rate, 2),
            'cache_hit_rate': round(self.cache_hit_rate, 2),
            'requests_by_type': self.requests_by_type,
            'provider_usage': self.provider_usage
        }

# ===== CACHE SYSTEM =====

class AIResponseCache:
    """Кэш ответов AI с TTL"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Tuple[AIResponse, float]] = {}
        self.access_times: Dict[str, float] = {}
    
    def _generate_key(self, request: AIRequest, user_context: str) -> str:
        """Генерация ключа кэша"""
        content = f"{request.message}:{request.request_type.value}:{user_context}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get(self, request: AIRequest, user_context: str) -> Optional[AIResponse]:
        """Получить ответ из кэша"""
        key = self._generate_key(request, user_context)
        
        if key in self.cache:
            response, timestamp = self.cache[key]
            
            # Проверяем TTL
            if time.time() - timestamp <= self.ttl_seconds:
                self.access_times[key] = time.time()
                response.cached = True
                return response
            else:
                # Удаляем устаревший элемент
                del self.cache[key]
                del self.access_times[key]
        
        return None
    
    def put(self, request: AIRequest, user_context: str, response: AIResponse) -> None:
        """Добавить ответ в кэш"""
        key = self._generate_key(request, user_context)
        
        # Если кэш переполнен, удаляем старые элементы
        if len(self.cache) >= self.max_size:
            self._evict_lru()
        
        current_time = time.time()
        self.cache[key] = (response, current_time)
        self.access_times[key] = current_time
    
    def _evict_lru(self) -> None:
        """Удалить наименее недавно использованный элемент"""
        if not self.access_times:
            return
        
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
        del self.cache[lru_key]
        del self.access_times[lru_key]
    
    def clear(self) -> None:
        """Очистить кэш"""
        self.cache.clear()
        self.access_times.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику кэша"""
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl_seconds
        }

# ===== RATE LIMITING =====

class RateLimiter:
    """Ограничитель скорости запросов"""
    
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[int, List[float]] = {}
    
    def is_allowed(self, user_id: int) -> bool:
        """Проверить, разрешен ли запрос"""
        current_time = time.time()
        
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # Удаляем старые запросы
        self.requests[user_id] = [
            req_time for req_time in self.requests[user_id]
            if current_time - req_time <= self.window_seconds
        ]
        
        # Проверяем лимит
        if len(self.requests[user_id]) >= self.max_requests:
            return False
        
        # Добавляем текущий запрос
        self.requests[user_id].append(current_time)
        return True
    
    def get_remaining_requests(self, user_id: int) -> int:
        """Получить количество оставшихся запросов"""
        if user_id not in self.requests:
            return self.max_requests
        
        current_time = time.time()
        recent_requests = [
            req_time for req_time in self.requests[user_id]
            if current_time - req_time <= self.window_seconds
        ]
        
        return max(0, self.max_requests - len(recent_requests))
    
    def get_reset_time(self, user_id: int) -> Optional[datetime]:
        """Получить время сброса лимита"""
        if user_id not in self.requests or not self.requests[user_id]:
            return None
        
        oldest_request = min(self.requests[user_id])
        reset_time = oldest_request + self.window_seconds
        return datetime.fromtimestamp(reset_time)

# ===== PROMPT MANAGER =====

class PromptManager:
    """Менеджер промптов с шаблонами"""
    
    def __init__(self):
        self.templates: Dict[PromptTemplate, str] = self._load_templates()
    
    def _load_templates(self) -> Dict[PromptTemplate, str]:
        """Загрузка шаблонов промптов"""
        return {
            PromptTemplate.SYSTEM_BASE: """Ты - AI-ассистент DailyCheck Bot, помогаешь пользователям с ежедневными задачами и привычками.

{user_context}

Правила поведения:
- Отвечай на русском языке
- Будь дружелюбным и поддерживающим
- Используй эмодзи для лучшего восприятия
- Давай конкретные и практичные советы
- Учитывай контекст пользователя в ответах
- Будь краток, но информативен (максимум 200 слов)""",

            PromptTemplate.MOTIVATION: """Твоя роль - МОТИВАТОР:

{user_context}

Задачи:
- Вдохновляй пользователя на выполнение задач
- Подчеркивай уже достигнутые успехи
- Давай конкретные советы по преодолению лени и прокрастинации
- Используй позитивный настрой
- Напоминай о долгосрочных целях и выгодах
- Предлагай маленькие шаги для начала

Стиль: энергичный, вдохновляющий, с личными примерами""",

            PromptTemplate.COACHING: """Твоя роль - КОУЧ ПО ПРОДУКТИВНОСТИ:

{user_context}

Задачи:
- Помогай планировать день и неделю
- Давай советы по организации времени
- Предлагай техники продуктивности (Pomodoro, GTD, Time Blocking)
- Анализируй текущие задачи и предлагай оптимизацию
- Помогай ставить реалистичные цели
- Обучай методам борьбы с отвлечениями

Стиль: структурированный, практичный, с конкретными рекомендациями""",

            PromptTemplate.PSYCHOLOGY: """Твоя роль - ПСИХОЛОГИЧЕСКИЙ ПОДДЕРЖИВАЮЩИЙ ПОМОЩНИК:

{user_context}

Задачи:
- Проявляй эмпатию и понимание
- Помогай справляться со стрессом и тревогой
- Предлагай техники релаксации и mindfulness
- Поддерживай ментальное здоровье
- Помогай разобраться с эмоциями
- Предлагай здоровые способы справления с трудностями

ВАЖНО: НЕ давай медицинских советов, направляй к специалистам при серьезных проблемах

Стиль: заботливый, понимающий, с техниками самопомощи""",

            PromptTemplate.ANALYSIS: """Твоя роль - АНАЛИТИК ПРОГРЕССА:

{user_context}

Задачи:
- Анализируй статистику и прогресс пользователя
- Выявляй паттерны в выполнении задач
- Предлагай способы улучшения результатов
- Указывай на сильные стороны и зоны роста
- Давай рекомендации на основе данных
- Помогай интерпретировать метрики

Стиль: аналитический, основанный на данных, с конкретными выводами""",

            PromptTemplate.TASK_SUGGESTION: """Ты - эксперт по планированию задач. На основе информации о пользователе предложи 5 подходящих ежедневных задач{category_filter}.

{user_context}

Требования к задачам:
- Конкретные и выполнимые
- Подходящие для ежедневного выполнения
- Учитывающие текущий уровень пользователя
- Разнообразные по типу деятельности
- Мотивирующие и полезные

Формат ответа:
- Каждая задача в одну строку
- Без нумерации и дополнительных символов
- Максимум 50 символов на задачу""",

            PromptTemplate.GENERAL: """Отвечай как дружелюбный помощник:

{user_context}

Задачи:
- Помогай с вопросами о боте и его функциях
- Поддерживай общение о задачах и привычках
- Предлагай полезные советы по продуктивности
- Будь позитивным и мотивирующим
- Отвечай на общие вопросы о саморазвитии

Стиль: дружелюбный, информативный, полезный"""
        }
    
    def get_prompt(self, template: PromptTemplate, user_context: str, **kwargs) -> str:
        """Получить промпт по шаблону"""
        template_str = self.templates.get(template, self.templates[PromptTemplate.GENERAL])
        
        # Заменяем плейсхолдеры
        prompt = template_str.format(
            user_context=user_context,
            **kwargs
        )
        
        return prompt
    
    def add_template(self, template: PromptTemplate, content: str) -> None:
        """Добавить новый шаблон"""
        self.templates[template] = content
    
    def get_all_templates(self) -> Dict[str, str]:
        """Получить все шаблоны"""
        return {template.value: content for template, content in self.templates.items()}

# ===== REQUEST CLASSIFIER =====

class RequestClassifier:
    """Классификатор типов запросов"""
    
    def __init__(self):
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> Dict[AIRequestType, List[str]]:
        """Загрузка паттернов для классификации"""
        return {
            AIRequestType.MOTIVATION: [
                'мотива', 'поддержка', 'вдохнови', 'устал', 'лень', 'не хочу',
                'сил нет', 'помоги', 'motivation', 'inspire', 'support',
                'упал духом', 'депресс', 'грустно', 'не могу', 'тяжело',
                'нет настроения', 'прокрастина', 'откладыва'
            ],
            
            AIRequestType.COACHING: [
                'план', 'цел', 'продуктивн', 'задач', 'организ', 'время',
                'планиров', 'productivity', 'goal', 'planning', 'time',
                'эффективн', 'pomodoro', 'gtd', 'метод', 'техник',
                'управление временем', 'тайм-менеджмент', 'приоритет'
            ],
            
            AIRequestType.PSYCHOLOGY: [
                'стресс', 'тревог', 'депресс', 'грустно', 'одинок', 'страх',
                'психолог', 'emotion', 'stress', 'anxiety', 'sad',
                'волну', 'переживан', 'беспокой', 'нерв', 'расстроен',
                'злость', 'гнев', 'обида', 'разочаров'
            ],
            
            AIRequestType.ANALYSIS: [
                'прогресс', 'статистика', 'анализ', 'результат', 'достижен',
                'analysis', 'progress', 'stats', 'achievement',
                'отчет', 'метрик', 'показател', 'динамик', 'тенденц',
                'как дела', 'как успехи', 'что с прогрессом'
            ]
        }
    
    def classify(self, message: str, user: User) -> AIRequestType:
        """Классификация запроса"""
        message_lower = message.lower()
        
        # Подсчитываем совпадения для каждого типа
        type_scores = {}
        
        for request_type, keywords in self.patterns.items():
            score = 0
            for keyword in keywords:
                if keyword in message_lower:
                    score += 1
            
            if score > 0:
                type_scores[request_type] = score
        
        # Возвращаем тип с наибольшим количеством совпадений
        if type_scores:
            best_type = max(type_scores.keys(), key=lambda k: type_scores[k])
            return best_type
        
        return AIRequestType.GENERAL
    
    def add_pattern(self, request_type: AIRequestType, keywords: List[str]) -> None:
        """Добавить паттерны для типа запроса"""
        if request_type not in self.patterns:
            self.patterns[request_type] = []
        
        self.patterns[request_type].extend(keywords)

# ===== CONTEXT BUILDER =====

class ContextBuilder:
    """Строитель контекста пользователя"""
    
    @staticmethod
    def build_user_context(user: User) -> str:
        """Построение контекста пользователя"""
        completed_today = len(user.completed_tasks_today)
        active_tasks = len(user.active_tasks)
        
        max_streak = max([task.current_streak for task in user.active_tasks.values()] + [0])
        
        week_progress = user.get_week_progress()
        
        context_parts = [
            f"Информация о пользователе:",
            f"- Имя: {user.display_name}",
            f"- Уровень: {user.stats.level} ({user.stats.get_level_title()})",
            f"- Общий XP: {user.stats.total_xp}",
            f"- Выполнено задач всего: {user.stats.completed_tasks}",
            f"- Активных задач: {active_tasks}",
            f"- Выполнено сегодня: {completed_today}",
            f"- Максимальный streak: {max_streak} дней",
            f"- Прогресс недели: {week_progress['completed']}/{week_progress['goal']} задач",
            f"- Дней с регистрации: {user.stats.days_since_registration}"
        ]
        
        # Добавляем информацию о задачах
        if user.active_tasks:
            context_parts.append("")
            context_parts.append("Примеры текущих задач:")
            for i, task in enumerate(list(user.active_tasks.values())[:3]):
                status = "✅" if task.is_completed_today() else "⭕"
                context_parts.append(f"- {status} {task.title} (streak: {task.current_streak})")
        
        # Добавляем статистику по категориям
        if user.stats.tasks_by_category:
            context_parts.append("")
            context_parts.append("Активность по категориям:")
            for category, count in user.stats.tasks_by_category.items():
                if count > 0:
                    context_parts.append(f"- {category}: {count} задач")
        
        # Добавляем информацию о времени активности
        if user.stats.preferred_time_of_day:
            time_emoji = {
                "morning": "🌅",
                "afternoon": "☀️", 
                "evening": "🌙"
            }.get(user.stats.preferred_time_of_day, "🕐")
            context_parts.append(f"- Предпочитаемое время: {time_emoji} {user.stats.preferred_time_of_day}")
        
        return "\n".join(context_parts)
    
    @staticmethod
    def build_task_context(user: User, category: Optional[str] = None) -> str:
        """Построение контекста для предложения задач"""
        context = ContextBuilder.build_user_context(user)
        
        if category:
            category_tasks = [
                task for task in user.active_tasks.values() 
                if task.category == category
            ]
            if category_tasks:
                context += f"\n\nТекущие задачи в категории '{category}':\n"
                for task in category_tasks:
                    context += f"- {task.title}\n"
        
        return context

# ===== FALLBACK RESPONSES =====

class FallbackResponseProvider:
    """Провайдер резервных ответов"""
    
    def __init__(self):
        self.responses = self._load_responses()
    
    def _load_responses(self) -> Dict[AIRequestType, List[str]]:
        """Загрузка резервных ответов"""
        return {
            AIRequestType.MOTIVATION: [
                "💪 {name}, ты уже выполнил {completed_today} задач сегодня! Это отличный результат!",
                "🔥 Твой максимальный streak {max_streak} дней показывает, что ты способен на многое!",
                "⭐ Уровень {level} ({level_title}) - это результат твоей упорной работы!",
                "🎯 У тебя есть {active_tasks} активных задач. Каждая выполненная - шаг к цели!",
                "✨ Помни: прогресс важнее совершенства. Каждый шаг имеет значение!",
                "🚀 Ты уже на {completion_rate:.1f}% выполнил свои цели! Продолжай в том же духе!"
            ],
            
            AIRequestType.COACHING: [
                "📋 Попробуй технику Pomodoro: 25 минут работы, 5 минут отдыха. Это поможет сосредоточиться!",
                "🎯 Начни с самой важной задачи утром, когда энергии больше всего.",
                "📝 Планируй день с вечера - это экономит время и снижает стресс утром.",
                "⏰ Устанавливай конкретные временные рамки для каждой задачи.",
                "🔢 Правило 2 минут: если задача займет меньше 2 минут, делай её сразу!",
                "📊 Анализируй свою продуктивность в разное время дня и планируй соответственно."
            ],
            
            AIRequestType.PSYCHOLOGY: [
                "🤗 Помни: прогресс важнее совершенства. Каждый шаг имеет значение.",
                "🌱 Стресс - это нормально. Важно найти здоровые способы с ним справляться.",
                "💙 Ты делаешь все возможное, и этого достаточно. Будь добрее к себе.",
                "🧘 Попробуй технику глубокого дыхания: вдох на 4 счета, задержка на 4, выдох на 6.",
                "🌈 Плохие дни тоже важны - они помогают ценить хорошие моменты.",
                "💪 Ты сильнее, чем думаешь. Каждый вызов - возможность расти."
            ],
            
            AIRequestType.ANALYSIS: [
                "📊 За эту неделю ты выполнил {week_completed} из {week_goal} задач.",
                "📈 Твой completion rate: {completion_rate:.1f}% - продолжай в том же духе!",
                "🏆 У тебя {achievements_count} достижений - отличный прогресс!",
                "⏱️ В среднем ты активен {days_active} дней - отличная привычка!",
                "🎯 Самый продуктивный период: {preferred_time} - используй это время максимально!",
                "📋 Больше всего задач в категории: {top_category} - это твоя сильная сторона!"
            ],
            
            AIRequestType.GENERAL: [
                "👋 Привет, {name}! Как дела с задачами?",
                "🤖 Я здесь, чтобы помочь тебе с организацией дня и мотивацией!",
                "✨ Используй /help чтобы узнать все мои возможности.",
                "🎯 Готов помочь с планированием и выполнением задач!",
                "📈 Хочешь обсудить свой прогресс или нужна мотивация?",
                "💡 Могу предложить новые задачи или помочь с планированием!"
            ]
        }
    
    def get_response(self, request_type: AIRequestType, user: User) -> str:
        """Получить резервный ответ"""
        responses = self.responses.get(request_type, self.responses[AIRequestType.GENERAL])
        
        # Выбираем случайный ответ
        template = random.choice(responses)
        
        # Подставляем данные пользователя
        completed_today = len(user.completed_tasks_today)
        max_streak = max([task.current_streak for task in user.active_tasks.values()] + [0])
        week_progress = user.get_week_progress()
        
        # Находим самую популярную категорию
        top_category = "personal"
        if user.stats.tasks_by_category:
            top_category = max(user.stats.tasks_by_category.keys(), 
                             key=lambda k: user.stats.tasks_by_category[k])
        
        return template.format(
            name=user.display_name,
            completed_today=completed_today,
            max_streak=max_streak,
            level=user.stats.level,
            level_title=user.stats.get_level_title(),
            active_tasks=len(user.active_tasks),
            completion_rate=user.stats.completion_rate,
            week_completed=week_progress['completed'],
            week_goal=week_progress['goal'],
            achievements_count=len(user.achievements),
            days_active=user.stats.days_active,
            preferred_time=user.stats.preferred_time_of_day,
            top_category=top_category
        )
    
    def get_task_suggestions(self, category: Optional[str] = None) -> List[str]:
        """Получить резервные предложения задач"""
        suggestions = {
            "health": [
                "Выпить 8 стаканов воды",
                "Сделать 10-минутную зарядку",
                "Пройти 10,000 шагов",
                "Съесть порцию овощей",
                "Спать 8 часов"
            ],
            "work": [
                "Проверить и ответить на важные письма",
                "Выполнить приоритетную рабочую задачу",
                "Провести планирование на следующий день",
                "Изучить новый профессиональный материал",
                "Организовать рабочее место"
            ],
            "learning": [
                "Прочитать 20 страниц книги",
                "Изучить новые слова иностранного языка",
                "Посмотреть образовательное видео",
                "Решить задачи по математике",
                "Написать краткий конспект"
            ],
            "personal": [
                "Провести время с семьей/друзьями",
                "Медитировать 10 минут",
                "Записать 3 вещи, за которые благодарен",
                "Убрать в одной комнате",
                "Послушать любимую музыку"
            ],
            "finance": [
                "Проверить банковские счета",
                "Записать все расходы за день",
                "Отложить деньги в копилку",
                "Изучить инвестиционную статью",
                "Проанализировать месячный бюджет"
            ]
        }
        
        if category and category in suggestions:
            return suggestions[category]
        
        # Возвращаем случайные задачи из разных категорий
        all_tasks = []
        for tasks in suggestions.values():
            all_tasks.extend(tasks)
        
        return random.sample(all_tasks, min(5, len(all_tasks)))
# ===== ПРОДОЛЖЕНИЕ core/ai_service.py (Part 2/2) =====

# ===== MAIN AI SERVICE =====

class AIService:
    """Улучшенный сервис для работы с AI"""
    
    def __init__(self):
        # Инициализация компонентов
        self.openai_client = None
        self.enabled = self._initialize_openai()
        
        # Менеджеры и сервисы
        self.prompt_manager = PromptManager()
        self.classifier = RequestClassifier()
        self.context_builder = ContextBuilder()
        self.fallback_provider = FallbackResponseProvider()
        
        # Кэш и ограничения
        self.cache = AIResponseCache()
        self.rate_limiter = RateLimiter()
        
        # Статистика
        self.stats = AIStats()
        
        # Конфигурация
        self.max_retries = 3
        self.retry_delay = 1.0
        self.max_context_length = 4000
        
        logger.info(f"AI Service initialized - OpenAI: {'✅' if self.enabled else '❌'}")
    
    def _initialize_openai(self) -> bool:
        """Инициализация OpenAI клиента"""
        if not OPENAI_AVAILABLE:
            logger.warning("OpenAI library not available")
            return False
        
        if not config.ai.openai_api_key:
            logger.warning("OpenAI API key not configured")
            return False
        
        # Проверяем, что API ключ не равен BOT_TOKEN
        if config.ai.openai_api_key == config.telegram.bot_token:
            logger.warning("OPENAI_API_KEY matches BOT_TOKEN - AI functions disabled")
            return False
        
        try:
            self.openai_client = AsyncOpenAI(
                api_key=config.ai.openai_api_key,
                timeout=config.ai.request_timeout
            )
            logger.info("OpenAI client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            return False
    
    async def generate_response(self, message: str, user: User, 
                              request_type: Optional[AIRequestType] = None) -> AIResponse:
        """Генерация ответа с учетом контекста пользователя"""
        start_time = time.time()
        
        try:
            # Проверяем rate limiting
            if not self.rate_limiter.is_allowed(user.user_id):
                raise AIRateLimitError("Rate limit exceeded")
            
            # Классифицируем запрос если не указан тип
            if not request_type:
                request_type = self.classifier.classify(message, user)
            
            # Создаем объект запроса
            request = AIRequest(
                user_id=user.user_id,
                message=message,
                request_type=request_type
            )
            
            # Строим контекст пользователя
            user_context = self.context_builder.build_user_context(user)
            
            # Проверяем кэш
            cached_response = self.cache.get(request, user_context)
            if cached_response:
                self.stats.cached_responses += 1
                self.stats.total_requests += 1
                self._update_request_stats(request_type, AIProvider.FALLBACK)
                return cached_response
            
            # Генерируем ответ
            if self.enabled and config.ai.ai_chat_enabled:
                response = await self._generate_openai_response(request, user_context)
            else:
                response = self._generate_fallback_response(request, user)
            
            # Сохраняем в кэш
            self.cache.put(request, user_context, response)
            
            # Обновляем статистику
            response.response_time_ms = int((time.time() - start_time) * 1000)
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self._update_request_stats(request_type, response.provider)
            self._update_average_response_time(response.response_time_ms)
            
            return response
            
        except AIRateLimitError:
            # Возвращаем специальное сообщение о превышении лимита
            remaining = self.rate_limiter.get_remaining_requests(user.user_id)
            reset_time = self.rate_limiter.get_reset_time(user.user_id)
            
            content = f"🚫 Превышен лимит запросов к AI. Попробуйте позже.\n\n"
            if reset_time:
                content += f"⏰ Лимит обнулится в {reset_time.strftime('%H:%M')}"
            
            return AIResponse(
                content=content,
                request_type=request_type or AIRequestType.GENERAL,
                provider=AIProvider.FALLBACK,
                quality=ResponseQuality.POOR
            )
            
        except Exception as e:
            logger.error(f"AI service error: {e}")
            self.stats.failed_requests += 1
            
            # Возвращаем fallback ответ
            return self._generate_fallback_response(
                AIRequest(
                    user_id=user.user_id,
                    message=message,
                    request_type=request_type or AIRequestType.GENERAL
                ),
                user
            )
    
    async def _generate_openai_response(self, request: AIRequest, user_context: str) -> AIResponse:
        """Генерация ответа через OpenAI"""
        # Получаем промпт
        prompt_template = {
            AIRequestType.MOTIVATION: PromptTemplate.MOTIVATION,
            AIRequestType.COACHING: PromptTemplate.COACHING,
            AIRequestType.PSYCHOLOGY: PromptTemplate.PSYCHOLOGY,
            AIRequestType.ANALYSIS: PromptTemplate.ANALYSIS,
            AIRequestType.GENERAL: PromptTemplate.GENERAL
        }.get(request.request_type, PromptTemplate.GENERAL)
        
        system_prompt = self.prompt_manager.get_prompt(prompt_template, user_context)
        
        # Подготавливаем сообщения
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request.message}
        ]
        
        # Отправляем запрос с retry логикой
        for attempt in range(self.max_retries):
            try:
                response = await self.openai_client.chat.completions.create(
                    model=config.ai.openai_model,
                    messages=messages,
                    max_tokens=config.ai.openai_max_tokens,
                    temperature=0.7,
                    timeout=config.ai.request_timeout
                )
                
                ai_response_content = response.choices[0].message.content.strip()
                tokens_used = response.usage.total_tokens if response.usage else 0
                
                # Определяем качество ответа
                quality = self._assess_response_quality(ai_response_content, request)
                
                return AIResponse(
                    content=ai_response_content,
                    request_type=request.request_type,
                    provider=AIProvider.OPENAI,
                    quality=quality,
                    tokens_used=tokens_used
                )
                
            except openai.RateLimitError:
                logger.warning(f"OpenAI rate limit hit, attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    raise AIRateLimitError("OpenAI rate limit exceeded")
                    
            except openai.APITimeoutError:
                logger.warning(f"OpenAI timeout, attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise AIServiceError("OpenAI request timeout")
                    
            except Exception as e:
                logger.error(f"OpenAI API error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise AIProviderError(f"OpenAI API failed: {e}")
    
    def _generate_fallback_response(self, request: AIRequest, user: User) -> AIResponse:
        """Генерация резервного ответа"""
        content = self.fallback_provider.get_response(request.request_type, user)
        
        return AIResponse(
            content=content,
            request_type=request.request_type,
            provider=AIProvider.FALLBACK,
            quality=ResponseQuality.ACCEPTABLE
        )
    
    def _assess_response_quality(self, content: str, request: AIRequest) -> ResponseQuality:
        """Оценка качества ответа"""
        # Простая эвристическая оценка
        if len(content) < 20:
            return ResponseQuality.POOR
        elif len(content) < 50:
            return ResponseQuality.ACCEPTABLE
        elif len(content) < 200:
            return ResponseQuality.GOOD
        else:
            return ResponseQuality.EXCELLENT
    
    async def suggest_tasks(self, user: User, category: Optional[str] = None) -> List[str]:
        """Предложение задач на основе AI"""
        try:
            # Проверяем rate limiting
            if not self.rate_limiter.is_allowed(user.user_id):
                return self.fallback_provider.get_task_suggestions(category)
            
            if not self.enabled or not config.ai.ai_chat_enabled:
                return self.fallback_provider.get_task_suggestions(category)
            
            # Строим контекст для предложения задач
            user_context = self.context_builder.build_task_context(user, category)
            category_filter = f" в категории '{category}'" if category else ""
            
            # Получаем промпт
            prompt = self.prompt_manager.get_prompt(
                PromptTemplate.TASK_SUGGESTION, 
                user_context, 
                category_filter=category_filter
            )
            
            # Отправляем запрос
            response = await self.openai_client.chat.completions.create(
                model=config.ai.openai_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.8,
                timeout=config.ai.request_timeout
            )
            
            suggestions_text = response.choices[0].message.content.strip()
            suggestions = [s.strip() for s in suggestions_text.split('\n') if s.strip()]
            
            # Фильтруем и ограничиваем
            valid_suggestions = []
            for suggestion in suggestions:
                if 3 <= len(suggestion) <= 100:  # Разумная длина
                    valid_suggestions.append(suggestion)
                if len(valid_suggestions) >= 5:
                    break
            
            return valid_suggestions[:5] if valid_suggestions else self.fallback_provider.get_task_suggestions(category)
            
        except Exception as e:
            logger.error(f"AI task suggestion failed: {e}")
            return self.fallback_provider.get_task_suggestions(category)
    
    def _update_request_stats(self, request_type: AIRequestType, provider: AIProvider) -> None:
        """Обновление статистики запросов"""
        type_key = request_type.value
        if type_key not in self.stats.requests_by_type:
            self.stats.requests_by_type[type_key] = 0
        self.stats.requests_by_type[type_key] += 1
        
        provider_key = provider.value
        if provider_key not in self.stats.provider_usage:
            self.stats.provider_usage[provider_key] = 0
        self.stats.provider_usage[provider_key] += 1
    
    def _update_average_response_time(self, response_time_ms: int) -> None:
        """Обновление среднего времени ответа"""
        total_time = self.stats.average_response_time_ms * (self.stats.successful_requests - 1)
        self.stats.average_response_time_ms = (total_time + response_time_ms) / self.stats.successful_requests
    
    # ===== PUBLIC API =====
    
    async def chat(self, message: str, user: User) -> str:
        """Простой интерфейс для чата"""
        response = await self.generate_response(message, user)
        return response.content
    
    async def get_motivation(self, user: User) -> str:
        """Получить мотивационное сообщение"""
        response = await self.generate_response(
            "Мотивируй меня выполнять задачи и быть продуктивным",
            user,
            AIRequestType.MOTIVATION
        )
        return response.content
    
    async def get_coaching(self, user: User) -> str:
        """Получить совет по продуктивности"""
        response = await self.generate_response(
            "Дай советы по продуктивности и планированию дня на основе моих задач",
            user,
            AIRequestType.COACHING
        )
        return response.content
    
    async def get_psychology_support(self, user: User) -> str:
        """Получить психологическую поддержку"""
        response = await self.generate_response(
            "Окажи психологическую поддержку и помоги справиться со стрессом",
            user,
            AIRequestType.PSYCHOLOGY
        )
        return response.content
    
    async def analyze_progress(self, user: User) -> str:
        """Проанализировать прогресс пользователя"""
        response = await self.generate_response(
            "Проанализируй мой прогресс и дай рекомендации",
            user,
            AIRequestType.ANALYSIS
        )
        return response.content
    
    def get_rate_limit_info(self, user_id: int) -> Dict[str, Any]:
        """Получить информацию о лимитах"""
        remaining = self.rate_limiter.get_remaining_requests(user_id)
        reset_time = self.rate_limiter.get_reset_time(user_id)
        
        return {
            'remaining_requests': remaining,
            'max_requests': self.rate_limiter.max_requests,
            'window_seconds': self.rate_limiter.window_seconds,
            'reset_time': reset_time.isoformat() if reset_time else None
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику AI сервиса"""
        return {
            'service': self.stats.to_dict(),
            'cache': self.cache.get_stats(),
            'enabled': self.enabled,
            'openai_available': OPENAI_AVAILABLE,
            'openai_configured': bool(config.ai.openai_api_key),
            'ai_chat_enabled': config.ai.ai_chat_enabled
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получить статус здоровья AI сервиса"""
        status = "healthy"
        issues = []
        
        # Проверяем доступность OpenAI
        if self.enabled and config.ai.ai_chat_enabled:
            if self.stats.success_rate < 80:
                status = "warning"
                issues.append("Low success rate")
        elif not OPENAI_AVAILABLE:
            status = "warning"
            issues.append("OpenAI library not available")
        elif not config.ai.openai_api_key:
            status = "warning"
            issues.append("OpenAI not configured")
        
        # Проверяем статистику ошибок
        if self.stats.failed_requests > self.stats.successful_requests * 0.1:
            status = "warning"
            issues.append("High error rate")
        
        return {
            'status': status,
            'issues': issues,
            'stats': self.get_stats(),
            'last_check': datetime.now().isoformat()
        }
    
    def clear_cache(self) -> None:
        """Очистить кэш ответов"""
        self.cache.clear()
        logger.info("AI response cache cleared")
    
    def reset_stats(self) -> None:
        """Сбросить статистику"""
        self.stats = AIStats()
        logger.info("AI service stats reset")
    
    # ===== CONFIGURATION =====
    
    def update_rate_limits(self, max_requests: int, window_seconds: int) -> None:
        """Обновить лимиты запросов"""
        self.rate_limiter = RateLimiter(max_requests, window_seconds)
        logger.info(f"Rate limits updated: {max_requests} requests per {window_seconds} seconds")
    
    def add_prompt_template(self, template: PromptTemplate, content: str) -> None:
        """Добавить новый шаблон промпта"""
        self.prompt_manager.add_template(template, content)
        logger.info(f"Added new prompt template: {template.value}")
    
    def add_classification_patterns(self, request_type: AIRequestType, keywords: List[str]) -> None:
        """Добавить паттерны для классификации"""
        self.classifier.add_pattern(request_type, keywords)
        logger.info(f"Added classification patterns for {request_type.value}")
    
    async def test_openai_connection(self) -> bool:
        """Тестирование подключения к OpenAI"""
        if not self.enabled:
            return False
        
        try:
            response = await self.openai_client.chat.completions.create(
                model=config.ai.openai_model,
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=10,
                timeout=5
            )
            return True
        except Exception as e:
            logger.error(f"OpenAI connection test failed: {e}")
            return False

# ===== CONVENIENCE FUNCTIONS =====

def create_ai_service() -> AIService:
    """Создать AI сервис"""
    return AIService()

async def quick_chat(message: str, user: User, ai_service: Optional[AIService] = None) -> str:
    """Быстрый чат с AI"""
    if not ai_service:
        ai_service = create_ai_service()
    
    return await ai_service.chat(message, user)

# ===== EXPORT =====

__all__ = [
    # Exceptions
    'AIServiceError',
    'AIProviderError', 
    'AIRateLimitError',
    'AIContextError',
    
    # Enums
    'AIProvider',
    'PromptTemplate',
    'ResponseQuality',
    
    # Data classes
    'AIRequest',
    'AIResponse',
    'AIStats',
    
    # Components
    'AIResponseCache',
    'RateLimiter',
    'PromptManager',
    'RequestClassifier',
    'ContextBuilder',
    'FallbackResponseProvider',
    
    # Main service
    'AIService',
    
    # Convenience functions
    'create_ai_service',
    'quick_chat'
]
