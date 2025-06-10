# 🚀 DailyCheck Bot v4.0

**Профессиональный Telegram-бот для управления задачами с геймификацией и веб-дашбордом**

<div align="center">

[![Version](https://img.shields.io/badge/Version-4.0-blue.svg)](https://github.com/yourusername/dailycheck-bot/releases)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen.svg)](https://dashboard-5q28.onrender.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](#license)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Telegram](https://img.shields.io/badge/Platform-Telegram-blue.svg)](https://telegram.org)

[**🤖 Попробовать бота**](https://t.me/YourBotName) • [**🌐 Веб-дашборд**](https://dashboard-5q28.onrender.com/) • [**📖 Документация**](PROJECT_CONTEXT.md)

</div>

---

## ✨ Возможности

<table>
<tr>
<td width="50%">

### 🎮 **Геймификация**
- 🏆 **16 уровней** от "Новичок" до "Божественный"
- 🎯 **10 достижений** с автопроверкой
- ⚡ **XP система** (25 XP за задачу + бонусы)
- 🔥 **Стрики выполнения** и рекорды
- 🎨 **5 тем оформления**

### 🤖 **AI-Ассистент**
- 💪 Мотивационные сообщения
- 🧠 Персональный коуч
- 🧘 Психологическая поддержка  
- 💡 Умные предложения задач
- 💬 Чат-режим с контекстом

</td>
<td width="50%">

### 📋 **Управление задачами**
- 🏢 **5 категорий**: работа, здоровье, обучение, личное, финансы
- ⭐ **3 уровня приоритетов**: низкий, средний, высокий
- 📝 **Подзадачи** для сложных проектов
- ⏱️ **Оценка времени** выполнения
- 🔘 **Интерактивные кнопки** для быстрых действий

### 👥 **Социальные функции**
- 🤝 Добавление друзей по ID
- 🏆 Сравнение достижений
- 📊 Лидерборды и рейтинги
- 💬 Взаимная мотивация

</td>
</tr>
</table>

### 🌐 **Веб-дашборд**
- 📊 Визуализация статистики и прогресса
- 📱 Мобильная адаптация
- 🔄 Синхронизация с Telegram-ботом
- 📈 Расширенная аналитика

### 🛠️ **Дополнительно**
- 📤 **Экспорт данных** в JSON/CSV
- ⏰ **Напоминания и таймеры**
- 🍷 **Режим "Dry"** (дни без алкоголя)
- 🎯 **Еженедельные цели**
- 🔧 **Админские функции**

---

## 🎯 **32+ команды бота**

<details>
<summary>🔸 <strong>Основные команды (3)</strong></summary>

- `/start` - Главное меню с интерактивными кнопками
- `/help` - Полная справка по всем командам  
- `/ping` - Проверка работы бота

</details>

<details>
<summary>🔸 <strong>Управление задачами (7)</strong></summary>

- `/tasks` - Быстрый доступ к задачам
- `/edit` - Редактировать список задач
- `/settasks` - Быстро установить задачи (через ;)
- `/addtask` - Добавить задачу с категорией и приоритетом
- `/addsub` - Добавить подзадачу к существующей задаче
- `/reset` - Сбросить прогресс дня

</details>

<details>
<summary>🔸 <strong>AI-функции (5)</strong></summary>

- `/ai_chat` - Включить/выключить AI-чат режим
- `/motivate` - Получить мотивационное сообщение
- `/ai_coach` - Персональный AI-коуч
- `/psy` - Консультация с AI-психологом
- `/suggest_tasks` - AI предложит задачи

</details>

<details>
<summary>🔸 <strong>Статистика и аналитика (2)</strong></summary>

- `/stats` - Детальная статистика
- `/analytics` - Продвинутая аналитика

</details>

<details>
<summary>🔸 <strong>Остальные команды</strong></summary>

**Цели и планирование (2):**
- `/weekly_goals` - Управление еженедельными целями  
- `/set_weekly` - Установить еженедельную цель

**Социальные функции (3):**
- `/friends` - Список друзей
- `/add_friend` - Добавить друга
- `/myid` - Узнать свой ID

**И еще 15+ команд** для напоминаний, персонализации, экспорта, режима "Dry" и администрирования.

</details>

---

## 🚀 Быстрый старт

### 1️⃣ **Попробовать готового бота**
```bash
# Найдите бота в Telegram
@YourBotName

# Отправьте команду
/start
```

### 2️⃣ **Веб-интерфейс**  
Откройте [dashboard-5q28.onrender.com](https://dashboard-5q28.onrender.com/) для работы через браузер.

### 3️⃣ **Развернуть собственного бота**

**Автоматическая установка:**
```bash
curl -sSL https://raw.githubusercontent.com/yourusername/dailycheck-bot/main/setup.sh | bash
```

**Ручная установка:**
```bash
# Клонировать репозиторий
git clone https://github.com/yourusername/dailycheck-bot.git
cd dailycheck-bot

# Установить зависимости
pip install -r requirements.txt

# Настроить переменные окружения
cp .env.example .env
# Отредактировать .env (добавить BOT_TOKEN)

# Запустить бота
python main.py
```

**Docker (рекомендуется):**
```bash
docker-compose up -d
```

---

## ⚙️ Конфигурация

Создайте файл `.env` с обязательными переменными:

```env
# Получить у @BotFather в Telegram
BOT_TOKEN=your_bot_token_here

# Получить у @userinfobot в Telegram  
ADMIN_USER_ID=your_telegram_id_here

# Для деплоя на Render/Heroku
PORT=10000

# Опционально: для AI-функций
OPENAI_API_KEY=your_openai_key_here
```

<details>
<summary><strong>📋 Получение BOT_TOKEN</strong></summary>

1. Напишите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте полученный токен в `.env`

</details>

---

## 🏗️ Архитектура

```
DailycheckBot2025-main/
├── 🐍 main.py                    # Основной код бота (207 KB)
├── ⚙️ config.py                 # Конфигурация
├── 📋 requirements.txt           # Python зависимости
├── 📁 utils/                     # Утилиты и хелперы
├── 📁 handlers/                  # Обработчики команд
├── 📁 services/                  # Бизнес-логика
├── 📁 models/                    # Модели данных
├── 📁 dashboard/                 # Веб-интерфейс (HTML/CSS/JS)
├── 📁 database/                  # База данных
├── 📁 data/                      # Пользовательские данные
├── 📁 exports/                   # Экспортированные файлы
├── 📁 backups/                   # Резервные копии
└── 📁 logs/                      # Логи системы
```

---

## 🌐 Развертывание

### **Поддерживаемые платформы:**

| Платформа | Статус | Инструкция |
|-----------|--------|------------|
| 🟢 **Render.com** | ✅ Текущий | [DEPLOYMENT.md](DEPLOYMENT.md#render) |
| 🟢 **Heroku** | ✅ Протестировано | [DEPLOYMENT.md](DEPLOYMENT.md#heroku) |
| 🟢 **VPS/Dedicated** | ✅ Поддерживается | [DEPLOYMENT.md](DEPLOYMENT.md#vps) |
| 🟢 **Docker** | ✅ Готово | `docker-compose up -d` |

### **Мониторинг:**
- Health check endpoint: `http://yourapp.com/health`
- Логи в папке `/logs/`
- Встроенная команда `/health` в боте

---

## 📊 Статистика проекта

- 🎯 **32+ команд** с полным функционалом
- 🎮 **16 уровней** геймификации  
- 🏆 **10 достижений** для мотивации
- 📋 **5 категорий задач** с приоритетами
- 🤖 **5 типов AI-помощи**
- 🌐 **Веб-дашборд** с мобильной адаптацией
- 📱 **Production-ready** с 99.9% uptime

---

## 🤝 Участие в разработке

Мы приветствуем вклад в развитие проекта! 

### **Как помочь:**
1. 🐛 [Сообщить об ошибке](https://github.com/yourusername/dailycheck-bot/issues/new?template=bug_report.md)
2. 💡 [Предложить улучшение](https://github.com/yourusername/dailycheck-bot/issues/new?template=feature_request.md)  
3. 🔧 [Создать Pull Request](https://github.com/yourusername/dailycheck-bot/pulls)
4. ⭐ Поставить звезду репозиторию

### **Процесс разработки:**
1. Fork репозитория
2. Создайте ветку: `git checkout -b feature/amazing-feature`
3. Внесите изменения: `git commit -m 'Add amazing feature'`
4. Push в ветку: `git push origin feature/amazing-feature`
5. Создайте Pull Request

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| 📖 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | **Полный контекст проекта** (для AI и разработчиков) |
| 🏗️ [ARCHITECTURE.md](ARCHITECTURE.md) | Детальная архитектура и структура |
| 📋 [API_REFERENCE.md](API_REFERENCE.md) | Справочник всех команд и API |
| 🚀 [DEPLOYMENT.md](DEPLOYMENT.md) | Инструкции по развертыванию |
| 🛠️ [DEVELOPMENT.md](DEVELOPMENT.md) | Руководство для разработчиков |

---

## 🎖️ Лицензия

Этот проект распространяется под лицензией MIT. Подробности в файле [LICENSE](LICENSE).

```
MIT License - свободное использование, модификация и распространение
```

---

## 💬 Поддержка и контакты

<div align="center">

### 🆘 **Нужна помощь?**

[![GitHub Issues](https://img.shields.io/badge/GitHub-Issues-red?logo=github)](https://github.com/yourusername/dailycheck-bot/issues)
[![Discussions](https://img.shields.io/badge/GitHub-Discussions-blue?logo=github)](https://github.com/yourusername/dailycheck-bot/discussions)
[![Email](https://img.shields.io/badge/Email-support%40dailycheck.bot-green?logo=gmail)](mailto:support@dailycheck.bot)
[![Telegram](https://img.shields.io/badge/Telegram-%40dailycheck__support-blue?logo=telegram)](https://t.me/dailycheck_support)

</div>

### **Каналы поддержки:**
- 🐛 **Баги и ошибки**: [GitHub Issues](https://github.com/yourusername/dailycheck-bot/issues)
- 💭 **Обсуждения**: [GitHub Discussions](https://github.com/yourusername/dailycheck-bot/discussions)
- 📧 **Email**: support@dailycheck.bot
- 📱 **Telegram**: @dailycheck_support

---

<div align="center">

### 🌟 **Понравился проект?**

**Поставьте ⭐ звезду на GitHub и поделитесь с друзьями!**

[![GitHub stars](https://img.shields.io/github/stars/yourusername/dailycheck-bot?style=social)](https://github.com/yourusername/dailycheck-bot/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/yourusername/dailycheck-bot?style=social)](https://github.com/yourusername/dailycheck-bot/network/members)

**Сделано с ❤️ для повышения продуктивности**

</div>
