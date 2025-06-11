"""
Сервис для работы с OpenAI API
"""

import random
import logging
from typing import List, Optional

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config import BotConfig, AIRequestType
from models import User

logger = logging.getLogger('dailycheck')

class AIService:
    """Сервис для работы с OpenAI API"""
    
    def __init__(self):
        self.client = None
        self.enabled = OPENAI_AVAILABLE and BotConfig.OPENAI_API_KEY
        
        # Проверяем, что API ключ не равен BOT_TOKEN
        if self.enabled and BotConfig.OPENAI_API_KEY == BotConfig.BOT_TOKEN:
            logger.warning("⚠️ OPENAI_API_KEY совпадает с BOT_TOKEN - AI функции отключены")
            self.enabled = False
        
        if self.enabled:
            try:
                self.client = AsyncOpenAI(api_key=BotConfig.OPENAI_API_KEY)
                logger.info("🤖 AI сервис инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации AI: {e}")
                self.enabled = False
        else:
            if not BotConfig.OPENAI_API_KEY:
                logger.warning("⚠️ AI сервис отключен (нет OPENAI_API_KEY)")
            elif BotConfig.OPENAI_API_KEY == BotConfig.BOT_TOKEN:
                logger.warning("⚠️ AI сервис отключен (OPENAI_API_KEY = BOT_TOKEN)")
            else:
                logger.warning("⚠️ AI сервис отключен (OpenAI недоступен)")
    
    def classify_request(self, message: str, user: User) -> AIRequestType:
        """Классификация типа запроса пользователя"""
        message_lower = message.lower()
        
        # Мотивационные запросы
        motivation_keywords = [
            'мотива', 'поддержка', 'вдохнови', 'устал', 'лень', 'не хочу',
            'сил нет', 'помоги', 'motivation', 'inspire', 'support'
        ]
        
        # Коучинг по продуктивности
        coaching_keywords = [
            'план', 'цел', 'продуктивн', 'задач', 'организ', 'время',
            'планиров', 'productivity', 'goal', 'planning', 'time'
        ]
        
        # Психологическая поддержка
        psychology_keywords = [
            'стресс', 'тревог', 'депресс', 'грустно', 'одинок', 'страх',
            'психолог', 'emotion', 'stress', 'anxiety', 'sad'
        ]
        
        # Анализ прогресса
        analysis_keywords = [
            'прогресс', 'статистика', 'анализ', 'результат', 'достижен',
            'analysis', 'progress', 'stats', 'achievement'
        ]
        
        for keyword in motivation_keywords:
            if keyword in message_lower:
                return AIRequestType.MOTIVATION
        
        for keyword in coaching_keywords:
            if keyword in message_lower:
                return AIRequestType.COACHING
        
        for keyword in psychology_keywords:
            if keyword in message_lower:
                return AIRequestType.PSYCHOLOGY
        
        for keyword in analysis_keywords:
            if keyword in message_lower:
                return AIRequestType.ANALYSIS
        
        return AIRequestType.GENERAL
    
    async def generate_response(self, message: str, user: User, 
                              request_type: Optional[AIRequestType] = None) -> str:
        """Генерация ответа с учетом контекста пользователя"""
        if not self.enabled:
            return self._get_fallback_response(message, user, request_type)
        
        try:
            if not request_type:
                request_type = self.classify_request(message, user)
            
            # Формируем контекст пользователя
            user_context = self._build_user_context(user)
            
            # Выбираем system prompt в зависимости от типа запроса
            system_prompt = self._get_system_prompt(request_type, user_context)
            
            # Формируем историю сообщений
            messages = [{"role": "system", "content": system_prompt}]
            
            # Добавляем последние сообщения из истории
            for msg in user.ai_chat_history[-5:]:  # Последние 5 сообщений
                messages.append(msg)
            
            messages.append({"role": "user", "content": message})
            
            # Отправляем запрос к OpenAI
            response = await self.client.chat.completions.create(
                model=BotConfig.OPENAI_MODEL,
                messages=messages,
                max_tokens=BotConfig.OPENAI_MAX_TOKENS,
                temperature=0.7,
                timeout=30
            )
            
            ai_response = response.choices[0].message.content.strip()
            
            # Сохраняем в историю чата
            user.ai_chat_history.append({"role": "user", "content": message})
            user.ai_chat_history.append({"role": "assistant", "content": ai_response})
            
            # Ограничиваем историю
            if len(user.ai_chat_history) > 20:
                user.ai_chat_history = user.ai_chat_history[-20:]
            
            return ai_response
            
        except Exception as e:
            logger.error(f"❌ Ошибка AI запроса: {e}")
            return self._get_fallback_response(message, user, request_type)
    
    def _build_user_context(self, user: User) -> str:
        """Построение контекста пользователя"""
        completed_today = len(user.completed_tasks_today)
        active_tasks = len(user.active_tasks)
        
        max_streak = max([task.current_streak for task in user.active_tasks.values()] + [0])
        
        week_progress = user.get_week_progress()
        
        context = f"""Информация о пользователе:
- Имя: {user.display_name}
- Уровень: {user.stats.level} ({user.stats.get_level_title()})
- Общий XP: {user.stats.total_xp}
- Выполнено задач всего: {user.stats.completed_tasks}
- Активных задач: {active_tasks}
- Выполнено сегодня: {completed_today}
- Максимальный streak: {max_streak} дней
- Прогресс недели: {week_progress['completed']}/{week_progress['goal']} задач
- Дней с регистрации: {user.stats.days_since_registration}"""
        
        if user.tasks:
            context += "\n\nПримеры текущих задач:"
            for i, task in enumerate(list(user.active_tasks.values())[:3]):
                status = "✅" if task.is_completed_today() else "⭕"
                context += f"\n- {status} {task.title} (streak: {task.current_streak})"
        
        return context
    
    def _get_system_prompt(self, request_type: AIRequestType, user_context: str) -> str:
        """Получение system prompt в зависимости от типа запроса"""
        base_prompt = f"""Ты - AI-ассистент DailyCheck Bot, помогаешь пользователям с ежедневными задачами и привычками.

{user_context}

Отвечай на русском языке, будь дружелюбным и поддерживающим. Используй эмодзи для лучшего восприятия."""
        
        if request_type == AIRequestType.MOTIVATION:
            return base_prompt + """

Твоя роль - МОТИВАТОР:
- Вдохновляй пользователя на выполнение задач
- Подчеркивай уже достигнутые успехи
- Давай конкретные советы по преодолению лени
- Используй позитивный настрой
- Напоминай о долгосрочных целях"""
        
        elif request_type == AIRequestType.COACHING:
            return base_prompt + """

Твоя роль - КОУЧ ПО ПРОДУКТИВНОСТИ:
- Помогай планировать день и неделю
- Давай советы по организации времени
- Предлагай техники продуктивности (Pomodoro, GTD, etc.)
- Анализируй текущие задачи и предлагай оптимизацию
- Помогай ставить реалистичные цели"""
        
        elif request_type == AIRequestType.PSYCHOLOGY:
            return base_prompt + """

Твоя роль - ПСИХОЛОГИЧЕСКИЙ ПОДДЕРЖИВАЮЩИЙ ПОМОЩНИК:
- Проявляй эмпатию и понимание
- Помогай справляться со стрессом и тревогой
- Предлагай техники релаксации и mindfulness
- Поддерживай ментальное здоровье
- НЕ давай медицинских советов, направляй к специалистам при серьезных проблемах"""
        
        elif request_type == AIRequestType.ANALYSIS:
            return base_prompt + """

Твоя роль - АНАЛИТИК ПРОГРЕССА:
- Анализируй статистику и прогресс пользователя
- Выявляй паттерны в выполнении задач
- Предлагай способы улучшения результатов
- Указывай на сильные стороны и зоны роста
- Давай рекомендации на основе данных"""
        
        else:  # GENERAL
            return base_prompt + """

Отвечай как дружелюбный помощник:
- Помогай с вопросами о боте и его функциях
- Поддерживай общение о задачах и привычках
- Предлагай полезные советы по продуктивности
- Будь позитивным и мотивирующим"""
    
    def _get_fallback_response(self, message: str, user: User, 
                             request_type: Optional[AIRequestType] = None) -> str:
        """Резервные ответы когда AI недоступен"""
        if not request_type:
            request_type = self.classify_request(message, user)
        
        completed_today = len(user.completed_tasks_today)
        active_tasks = len(user.active_tasks)
        max_streak = max([task.current_streak for task in user.active_tasks.values()] + [0])
        
        if request_type == AIRequestType.MOTIVATION:
            responses = [
                f"💪 {user.display_name}, ты уже выполнил {completed_today} задач сегодня! Это отличный результат!",
                f"🔥 Твой максимальный streak {max_streak} дней показывает, что ты способен на многое!",
                f"⭐ Уровень {user.stats.level} ({user.stats.get_level_title()}) - это результат твоей упорной работы!",
                f"🎯 У тебя есть {active_tasks} активных задач. Каждая выполненная - шаг к цели!"
            ]
        elif request_type == AIRequestType.COACHING:
            responses = [
                "📋 Попробуй технику Pomodoro: 25 минут работы, 5 минут отдыха. Это поможет сосредоточиться!",
                "🎯 Начни с самой важной задачи утром, когда энергии больше всего.",
                "📝 Планируй день с вечера - это экономит время и снижает стресс утром.",
                "⏰ Устанавливай конкретные временные рамки для каждой задачи."
            ]
        elif request_type == AIRequestType.PSYCHOLOGY:
            responses = [
                "🤗 Помни: прогресс важнее совершенства. Каждый шаг имеет значение.",
                "🌱 Стресс - это нормально. Важно найти здоровые способы с ним справляться.",
                "💙 Ты делаешь все возможное, и этого достаточно. Будь добрее к себе.",
                "🧘 Попробуй технику глубокого дыхания: вдох на 4 счета, задержка на 4, выдох на 6."
            ]
        elif request_type == AIRequestType.ANALYSIS:
            week_progress = user.get_week_progress()
            responses = [
                f"📊 За эту неделю ты выполнил {week_progress['completed']} из {week_progress['goal']} задач.",
                f"📈 Твой completion rate: {user.stats.completion_rate:.1f}% - продолжай в том же духе!",
                f"🏆 У тебя {len(user.achievements)} достижений из количества возможных.",
                f"⏱️ В среднем ты активен {user.stats.days_since_registration} дней - отличная привычка!"
            ]
        else:
            responses = [
                f"👋 Привет, {user.display_name}! Как дела с задачами?",
                "🤖 Я здесь, чтобы помочь тебе с организацией дня и мотивацией!",
                "✨ Используй /help чтобы узнать все мои возможности.",
                "🎯 Готов помочь с планированием и выполнением задач!"
            ]
        
        return random.choice(responses)
    
    async def suggest_tasks(self, user: User, category: Optional[str] = None) -> List[str]:
        """Предложение задач на основе AI"""
        if not self.enabled:
            return self._get_fallback_task_suggestions(category)
        
        try:
            user_context = self._build_user_context(user)
            category_filter = f" в категории '{category}'" if category else ""
            
            prompt = f"""На основе информации о пользователе предложи 5 подходящих ежедневных задач{category_filter}.

{user_context}

Требования:
- Задачи должны быть конкретными и выполнимыми
- Учитывай текущий уровень пользователя
- Предлагай разнообразные задачи
- Каждая задача в одну строку
- Без нумерации и дополнительных символов"""
            
            response = await self.client.chat.completions.create(
                model=BotConfig.OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.8
            )
            
            suggestions = response.choices[0].message.content.strip().split('\n')
            return [s.strip() for s in suggestions if s.strip()][:5]
            
        except Exception as e:
            logger.error(f"❌ Ошибка AI предложений задач: {e}")
            return self._get_fallback_task_suggestions(category)
    
    def _get_fallback_task_suggestions(self, category: Optional[str] = None) -> List[str]:
        """Резервные предложения задач"""
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
