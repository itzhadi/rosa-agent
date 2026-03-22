# Neurogenic Rosacea Daily Agent

הסקריפט הזה מחפש פעם ביום:
- מאמרים חדשים ב-PubMed על neurogenic rosacea / neuropathic rosacea / small fiber neuropathy
- ואופציונלית גם חדשות רלוונטיות דרך Tavily

ואז:
- מסנן כפילויות
- מסכם את מה שחדש בלבד
- שומר קובץ Markdown יומי

## קבצים שנוצרים
- `digest_YYYY-MM-DD.md` — הסיכום היומי
- `raw_YYYY-MM-DD.json` — הנתונים הגולמיים
- `seen_items.json` — מזהי פריטים שכבר סוכמו

## התקנה
```bash
python -m venv .venv
source .venv/bin/activate
# ב-Windows:
# .venv\Scripts\activate

pip install openai requests
```

## env
צור קובץ `.env` או הגדר משתני סביבה:

```bash
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-5
NCBI_EMAIL=your@email.com
TAVILY_API_KEY=your_tavily_key   # אופציונלי
```

## הרצה
```bash
python neurogenic_rosacea_agent.py --output-dir ./rosacea_digests
```

## הרצה יומית אוטומטית

### Windows Task Scheduler
צור משימה יומית שמריצה:
```bash
python C:\path\to\neurogenic_rosacea_agent.py --output-dir C:\path\to\rosacea_digests
```

### Linux / Mac cron
```cron
0 8 * * * /usr/bin/python3 /path/to/neurogenic_rosacea_agent.py --output-dir /path/to/rosacea_digests
```

## הערות
- בלי `TAVILY_API_KEY` יעבוד רק על PubMed.
- זה כלי מעקב ומידע, לא אבחון רפואי.
- אם תרצה, אפשר לשדרג אותו שישלח לך את התקציר לטלגרם, ג'ימייל, או דיסקורד.
