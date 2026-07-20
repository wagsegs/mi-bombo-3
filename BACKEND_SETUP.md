# MI BOMBO Studios Backend Implementation - Setup Checklist

## ✅ Implementation Complete

### Core Modules Created
- ✅ `database.py` - PostgreSQL/Supabase connection & operations
- ✅ `ai/text_provider.py` - Pollinations text integration
- ✅ `ai/image_provider.py` - Pollinations image integration
- ✅ `progression.py` - Screen time & promotion system
- ✅ `tracking.py` - Message tracking & conversation grouping
- ✅ `scheduler.py` - Scheduled jobs (newspaper, weekly cast)
- ✅ `cogs/message_listener.py` - Message tracking listener
- ✅ `config.py` - Updated with all role IDs & constants
- ✅ `bot.py` - Integrated all systems

### Features Implemented
✅ Message tracking (stores all non-bot messages)
✅ Screen time system (modular bonus calculations)
✅ Automatic role progression (mutually exclusive roles)
✅ Daily newspaper generation at 09:00 Europe/Berlin
✅ Weekly cast generation at 09:00 Sundays Europe/Berlin
✅ Conversation tracking (foundation for Quote Game, etc.)
✅ Error handling & logging
✅ Database auto-initialization on startup

---

## 🚀 Required Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create `.env` File (CRITICAL)
Add these environment variables:

```env
# Discord
DISCORD_TOKEN=your_bot_token_here
PREFIX=.

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://user:password@host:port/database_name

# Pollinations AI
POLLINATIONS_BASE_URL=https://image.pollinations.ai
POLLINATIONS_TEXT_BASE_URL=https://text.pollinations.ai
POLLINATIONS_IMAGE_BASE_URL=https://image.pollinations.ai

# Server Config
SERVER_ID=1526652261764173874
CASTING_CHANNEL_ID=1527244160917045278
NEWSPAPER_CHANNEL_ID=1526652930604662955
WEEKLY_CAST_CHANNEL_ID=1526652930604662955

# Existing Config (keep as-is)
KLIPY_URL=your_klipy_url
KLIPY_KEY=your_klipy_key
WELCOME_CHANNEL_ID=1526652261764173877
```

### 3. Database Setup
- Create a PostgreSQL database (use Supabase or similar)
- Tables are auto-created on first bot startup
- No manual SQL required

### 4. Verify Configuration
- Make sure all progression role IDs in `config.py` are correct for your server
- Verify channel IDs for casting, newspaper, and weekly cast channels
- Test that bot has permissions in those channels

---

## 🔧 How It Works

### Message Processing Flow
```
User sends message
    ↓
Message Listener catches it
    ↓
Save to database
    ↓
Calculate screen time (modular bonuses)
    ↓
Award points to user
    ↓
Check if they should be promoted
    ↓
If yes: Remove old role → Add new role → Post casting update
```

### Scheduled Jobs
```
Daily (09:00):
  - Read last 24 hours of messages
  - Ask the Studio text provider to summarize
  - Generate newspaper image
  - Post to #newspapers
  - Save to database

Weekly (Sunday 09:00):
  - Read last 7 days of messages
  - Ask the Studio text provider to select 5-7 cast members
  - Generate anime poster (different style each week)
  - Post to #newspapers
  - Save to database
```

---

## 📊 Screen Time System

### How Points Are Awarded
For each message, users earn points from:
- **Conversation Bonus** (1-5 points based on length)
- **Participant Bonus** (1-5 points based on conversation size)
- **Length Bonus** (1-5 points based on message length)
- **Revival Bonus** (2 points for replying to old messages)

Future bonuses (placeholders):
- AI-based quality bonus
- Reaction-based bonus

### Progression Roles (Mutually Exclusive)
1. members (0 ST)
2. Extra (100 ST)
3. Guest Star (250 ST)
4. Supporting Cast (500 ST)
5. Main Cast (1000 ST)
6. Main Character (2000 ST)
7. Fan Favorite (3500 ST)
8. Scene Stealer (5500 ST)
9. Box Office Legend (8000 ST)
10. Hall of Fame (12000 ST)

**Important:** Users can ONLY have ONE at a time. Promotion removes old role automatically.

---

## 🎮 User Commands

```
.screentime              - Check your screen time
.screentime @username   - Check someone else's screen time
.st                     - Shorthand for .screentime
```

---

## 📝 Testing

Before running in production:

1. **Test Database Connection**
   - Ensure DATABASE_URL is correct
   - Check Supabase connection status

2. **Test Pollinations Integration**
   - Verify Pollinations environment variables are valid
   - Check API quota

3. **Test Bot Permissions**
   - Bot should have permission to:
     - Send messages in all tracked channels
     - Manage roles in the server
     - View message history

4. **Test Message Tracking**
   - Send a test message
   - Check if `.screentime` shows data

5. **Test Promotion**
   - Monitor logs for screen time awards
   - Manually test with owner command: `.checkprogression`

---

## 🐛 Common Issues

### "Database not connected" Error
- Check DATABASE_URL in .env
- Verify PostgreSQL server is running
- Check connection string format

### "Pollinations failed" Error
- Check Pollinations environment variables in .env
- Check API quota on Google Cloud
- Check internet connection

### "Missing permissions" Error
- Bot needs these permissions:
  - Send Messages
  - Embed Links
  - Manage Roles (for promotions)
  - Read Message History

### Roles not being assigned
- Check role IDs are correct in config.py
- Verify bot role is above progression roles in server hierarchy
- Check bot has "Manage Roles" permission

---

## 🔐 Important Notes

⚠️ **DO NOT:**
- Edit role IDs directly in messages
- Manually give progression roles with bot permission
- Disable user mentions in message sends
- Keep provider calls inside `ai/text_provider.py` and `ai/image_provider.py`
- Scatter database calls throughout cogs

✅ **DO:**
- Keep environment variables secure
- Test thoroughly before production
- Monitor logs for errors
- Update role thresholds in config.py as needed
- Keep provider prompts updated

---

## 📚 System Architecture

See `/memories/repo/MI_BOMBO_backend_architecture.md` for detailed architecture documentation.

Key principles:
- **Modular** - Easy to add new systems
- **Centralized** - All DB/AI ops go through modules
- **Deterministic** - No random behavior
- **Error-resilient** - Graceful failure handling

---

## 🚀 What's Next?

The system is designed to easily support:
- Quote Game (uses message tracking)
- Achievements system
- Events/Quests
- Movie Awards
- Lore expansion
- Reaction-based bonuses
- AI quality-based bonuses

No refactoring needed - just add new modules!

---

## 📞 Support

If something breaks:
1. Check the logs (enable DEBUG mode if needed)
2. Verify all environment variables are set
3. Check database connection
4. Make sure all required tables exist (auto-created on startup)
5. Verify Discord bot token and permissions

Good luck! 🎬
