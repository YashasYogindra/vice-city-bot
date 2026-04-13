# sinbot/gifs.py
# =============================================================
# SINBOT — CENTRAL GIF / IMAGE REGISTRY
# =============================================================
# One file. Every command. Paste a direct media URL (ending in
# .gif / .png / .jpg / .webp) inside the quotes for each key.
#
# Rules:
#
#   • Leave a key as "" to silently skip the image — no crash.
#   • Use direct media URLs, NOT share/watch pages.
#     ✅  https://media.giphy.com/media/.../giphy.gif
#     ❌  https://giphy.com/gifs/some-slug
#   • Tenor: append ?itemid=...&ct=g to get a direct URL,
#     or use the "Media URL" button and grab the .gif link.
#   • One URL per key — copy-paste, save, restart the bot.
# =============================================================


# ── CORE ─────────────────────────────────────────────────────

# /join — shown when a new player joins the city
JOIN_CITY = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExeG1sdTlqaWdhcTAzenl4M3ZmYjR6am04anA2cmZocmJxa3pzMXF6eSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/xFj5OOi0oqQ48/giphy.gif"

# /profile — thumbnail on the profile card embed
PROFILE_CARD = ""

# /wallet — shown when viewing your balance
WALLET_VIEW = "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExb3N1b2Zvb251b21uMGoxaWx4bXBxajVkNTB5d2JndTIxa3cxOXE5ZyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3orifdO6eKr9YBdOBq/giphy.gif"

# /daily — daily reward claimed
DAILY_STREAK = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExMXRyN3YzNXhqemQ0YWlvcW41Y25pbm9lZTNkZ3lyeGlsNnZjN3JqZiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/eIFw4ALINJkQg6BDV8/giphy.gif"

# /gang — gang overview
GANG_VIEW = ""

# /gang deposit — Racks deposited into gang bank
GANG_DEPOSIT = ""

# /gang withdraw — Racks withdrawn from gang bank
GANG_WITHDRAW = ""

# /pay — money sent to another player
PAY_SENT = ""

# /map — city turf map
CITY_MAP = ""

# /news — city news feed
CITY_NEWS = "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExYW85cmVtbzdpZGJheThkbzg2NG5xM3VwMWpicTUxZnQzbXBsbHNobCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9cw/DuG9z3cK5UFkQ/giphy.gif"

# /wanted — most wanted board
WANTED_BOARD = ""

# /leaderboard — XP/wealth rankings
LEADERBOARD = ""

# /shop — black market shop menu
SHOP_VIEW = ""

# /buy — item purchased from shop
ITEM_BOUGHT = "https://media0.giphy.com/media/v1.Y2lkPTc5MGI3NjExeDB2cHN2aXY1a2Jna2hleDk4dWpkazNyZDIzYXl5dng4MTc5OWl2aiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/H5iCLJ4AyqH2MsAERZ/giphy.gif"

# /tip — street informant tip
STREET_TIP = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXl2NzgyczRkc2tjMHYxbXphY3U3ZTk1OTM2bXlxMm91NDdyZGttdiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/A06UFEx8jxEwU/giphy.gif"

# /advise — AI consigliere strategic advice
CONSIGLIERE = ""

# /bail — paid bail to exit jail
BAIL_OUT = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa3NkMHo0a2Jpcm8xazl4ZWVoZGYzaGxxdGs2OGwwOHc1cnFnc3U5diZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Ncn7y0xz7ZfAxEcEml/giphy.gif"

# /tension — city violence level meter
TENSION_METER = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXlubzV1cDI1N2pkdnJlMXBub3NjNDZwOXI4MnZvbHpzamdiaHRoYiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/x0GeFXErpcRk4/giphy.gif"


# ── OPERATIONS ───────────────────────────────────────────────

# /operate drug — successful drug run
DRUG_RUN_SUCCESS = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExaWQxemZsZm56aWF3cTlzbHAxbXluODR5dHozaXZxdWRxaWV2MXlsaCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/3o8dFzIXb0qaE3pYWs/giphy.gif"

# /operate drug — busted on a drug run
DRUG_RUN_BUSTED = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcGtoY3dsdng1Mnh1Ym9wMGgydzF5c295aWQ0OTBocDdqNGIxbDFndCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ziNUOin6TC30HRQVHk/giphy.gif"

# /operate arms — successful arms deal
ARMS_DEAL_SUCCESS = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa3NkMHo0a2Jpcm8xazl4ZWVoZGYzaGxxdGs2OGwwOHc1cnFnc3U5diZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Ncn7y0xz7ZfAxEcEml/giphy.gif"

# /operate arms — busted on an arms deal
ARMS_DEAL_BUSTED = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcGtoY3dsdng1Mnh1Ym9wMGgydzF5c295aWQ0OTBocDdqNGIxbDFndCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ziNUOin6TC30HRQVHk/giphy.gif"

# Interrogation view (bust negotiation)
INTERROGATION = "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExMDA0cWszZzZkMTU5MWZwdXk1ZnZlZm5taTJ4Ync5Y3NnNmUxMjBzOCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o6Zt2rgbz7mb5HooU/giphy.gif"


# ── FIGHTING ─────────────────────────────────────────────────

# /fight — challenge embed sent to opponent
FIGHT_CHALLENGE = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZWg2a3Nzbmh6a2RieDdldDd0OTc0OGVxcmNoOWY4b29tMjd6eW93MCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/d6K34dPHWbEo0oYcie/giphy.gif"

# /fight — each round result
FIGHT_ROUND = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZWg2a3Nzbmh6a2RieDdldDd0OTc0OGVxcmNoOWY4b29tMjd6eW93MCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/d6K34dPHWbEo0oYcie/giphy.gif"

# /fight — fight over, winner declared
FIGHT_KNOCKOUT = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcGtoY3dsdng1Mnh1Ym9wMGgydzF5c295aWQ0OTBocDdqNGIxbDFndCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ziNUOin6TC30HRQVHk/giphy.gif"


# ── WAR ──────────────────────────────────────────────────────

# /attack — turf war declared
WAR_DECLARE = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExc2Yxb2cyZTczZ3lwNnQ3NjAxemE4azdxcmR3b3M3YjQwaWp5ZnI1cSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/PtFk5J9VbRJeijlbQn/giphy.gif"

# /assault or /defend — player commits to war
WAR_JOIN = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExc2Yxb2cyZTczZ3lwNnQ3NjAxemE4azdxcmR3b3M3YjQwaWp5ZnI1cSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/PtFk5J9VbRJeijlbQn/giphy.gif"

# War resolved — winning side announced
WAR_VICTORY = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExc2Yxb2cyZTczZ3lwNnQ3NjAxemE4azdxcmR3b3M3YjQwaWp5ZnI1cSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/PtFk5J9VbRJeijlbQn/giphy.gif"


# ── HEIST ────────────────────────────────────────────────────

# /heist plan — heist planning channel created
HEIST_PLAN = ""

# /heist join — player joins a heist role
HEIST_JOIN = "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExZDAwa3FtbXhwYjQ0MjY1bDhoZmQ0eHF1dDE5Znoyd295dXdwNTY1eSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/nsujw39TotM9tGfFlP/giphy.gif"

# /heist go — heist launched, crew moving
HEIST_PLANNING = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa3NkMHo0a2Jpcm8xazl4ZWVoZGYzaGxxdGs2OGwwOHc1cnFnc3U1diZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Ncn7y0xz7ZfAxEcEml/giphy.gif"

# Heist completed — payout received
HEIST_SUCCESS = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa3NkMHo0a2Jpcm8xazl4ZWVoZGYzaGxxdGs2OGwwOHc1cnFnc3U1diZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Ncn7y0xz7ZfAxEcEml/giphy.gif"

# Heist busted — crew caught
HEIST_BUSTED = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcGtoY3dsdng1Mnh1Ym9wMGgydzF5c295aWQ0OTBocDdqNGIxbDFndCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ziNUOin6TC30HRQVHk/giphy.gif"


# ── CASINO ───────────────────────────────────────────────────

# /casino slots, /casino flip, /casino duel — win
CASINO_WIN = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHBvbHdzM3ZueDhwNmtlb3BnY2NtaW5yMDBocGZoZmQ1ejlmdGZqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/xWMVIKpbpZ0SaEQClb/giphy.gif"

# /casino slots, /casino flip, /casino duel — loss
CASINO_LOSS = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcGtoY3dsdng1Mnh1Ym9wMGgydzF5c295aWQ0OTBocDdqNGIxbDFndCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ziNUOin6TC30HRQVHk/giphy.gif"

# /casino duel — challenge sent to opponent
CASINO_DUEL = "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3cxNnhxemg1emZ4aDBlNTlqdGtraXV5eXN3Zng4eWI2ZWJ4ZWpiOCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/2YHdXovMSv1NtO6V4n/giphy.gif"

# /casino blackjack — blackjack game started
CASINO_BLACKJACK = "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExeGQxNWE3ZmMxc2Fya29xNGppeGM3aWswMWNhN3E2bGIzbWRyaWIwcCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/5JLGh44QWB4mzj8M6l/giphy.gif"


# ── BETTING (IPL) ─────────────────────────────────────────────

# /bet ipl — live match fetched, ready to bet
BET_IPL = "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExcDhpNm5nbW13YnUzdWI5bmM5ZmZ2bGJtb3Ywd3A4MDg1MHhjazJhMSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/VaaZHPiUEAzv7nleyw/giphy.gif"

# /bet place — bet placed on a team
BET_PLACE = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eGdsdDZqbTVvbGtxYTQyNnV5cnI0bHVvaHB6Z2NtZzFyeW1kMzdkbyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/f8M7aATROMBFJnro0p/giphy.gif"

# /bets — viewing your active bet
BET_VIEW = "https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExbWxhYXpjYndmdmY0eGl4bjNtbzczOTlvOGVkNWN1cG41MmowZnh1YyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/RM5m5NoNRtuYCj1szf/giphy.gif"

# /resolvebets — bets resolved, winners paid
BET_WIN = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHBvbHdzM3ZueDhwNmtlb3BnY2NtaW5yMDBocGZoZmQ1ejlmdGZqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/xWMVIKpbpZ0SaEQClb/giphy.gif"


# ── SOCIAL ───────────────────────────────────────────────────

# /rat — rat report filed on a gang member
RAT_REPORT = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExejFma3ZrMDFhcGM5eHI3cnZidmJuc2Z4cWw1aGVveTk4cXQ5bTJweSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/uiw6yGczaRaJ0i47os/giphy.gif"

# /vote exile — exile vote cast
EXILE_VOTE = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcGtoY3dsdng1Mnh1Ym9wMGgydzF5c295aWQ0OTBocDdqNGIxbDFndCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ziNUOin6TC30HRQVHk/giphy.gif"

# /challenge boss — leadership challenge started or joined
BOSS_CHALLENGE = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExc2Yxb2cyZTczZ3lwNnQ3NjAxemE4azdxcmR3b3M3YjQwaWp5ZnI1cSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/PtFk5J9VbRJeijlbQn/giphy.gif"


# ── BLACK MARKET & AUCTION ───────────────────────────────────

# /buy — item purchased from the black market
MARKET_PURCHASE = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa3NkMHo0a2Jpcm8xazl4ZWVoZGYzaGxxdGs2OGwwOHc1cnFnc3U1diZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Ncn7y0xz7ZfAxEcEml/giphy.gif"

# /auction — harbour auction opened
AUCTION_START = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOWp5ZTlraHRicWhtZWI3aHQ2Zmo3ZGd1b3cwZ2E4N205NGJuMXBubyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/OU8nFZNCcgaFr2WcJR/giphy.gif"

# /auction — item sold to highest bidder
AUCTION_SOLD = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExOWp5ZTlraHRicWhtZWI3aHQ2Zmo3ZGd1b3cwZ2E4N205NGJuMXBubyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/OU8nFZNCcgaFr2WcJR/giphy.gif"


# ── MAYOR & CITY ADMIN ───────────────────────────────────────

# /mayor tax — tax rate updated
MAYOR_TAX = ""

# /mayor crackdown — police crackdown activated
CRACKDOWN = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXlubzV1cDI1N2pkdnJlMXBub3NjNDZwOXI4MnZvbHpzamdiaHRoYiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/x0GeFXErpcRk4/giphy.gif"

# /mayor pardon — player released by mayor
MAYOR_PARDON = "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExNzA5b3F4c2l5eWcxenpybHJsMmF0Zm9wNjEybWQ4N3YzZHBuMmZjZyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3oriO5sZ43mUXSHrkk/giphy.gif"

# /mayor reward — gang rewarded from treasury
TREASURY_REWARD = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcHBvbHdzM3ZueDhwNmtlb3BnY2NtaW5yMDBocGZoZmQ1ejlmdGZqYSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/xWMVIKpbpZ0SaEQClb/giphy.gif"

# /bribe mayor — bribe submitted
BRIBE_SENT = "https://media.giphy.com/media/v1.Y2lkPWVjZjA1ZTQ3eGdsdDZqbTVvbGtxYTQyNnV5cnI0bHVvaHB6Z2NtZzFyeW1kMzdkbyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/f8M7aATROMBFJnro0p/giphy.gif"

# /city event — active city event displayed
CITY_EVENT = ""


# ── CITY EVENTS (auto-triggered) ─────────────────────────────

# Police Sweep city event
POLICE_SWEEP = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXlubzV1cDI1N2pkdnJlMXBub3NjNDZwOXI4MnZvbHpzamdiaHRoYiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/x0GeFXErpcRk4/giphy.gif"

# Black Market Sale city event
BLACK_MARKET_SALE = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExZjBvYnBhOG03bmt3M21uZ2JkaGVnMXBrbG1od2I5eTdyaWhzYWJjdCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/GaqnjVbSLs2uA/giphy.gif"

# Casino Rush city event
CASINO_RUSH = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExa3NkMHo0a2Jpcm8xazl4ZWVoZGYzaGxxdGs2OGwwOHc1cnFnc3U1diZlcD12MV9naWZzX3NlYXJjaCZjdD1n/Ncn7y0xz7ZfAxEcEml/giphy.gif"

# Harbor Shipment city event
HARBOR_SHIPMENT = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcnB1cnJkbjZzZW44ajYwZ2pmcnhyOXJhcThvd3NnZmNxZ2tjbGZpciZlcD12MV9naWZzX3NlYXJjaCZjdD1n/jYmGmDK3rKdkk/giphy.gif"

# Player hit Heat 5 — most wanted
MOST_WANTED = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExYXlubzV1cDI1N2pkdnJlMXBub3NjNDZwOXI4MnZvbHpzamdiaHRoYiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/x0GeFXErpcRk4/giphy.gif"

# Rat report — genuine tip confirmed
RAT_SUCCESS = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExejFma3ZrMDFhcGM5eHI3cnZidmJuc2Z4cWw1aGVveTk4cXQ5bTJweSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/uiw6yGczaRaJ0i47os/giphy.gif"

# Rat report — false tip dismissed
RAT_FALSE_TIP = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcGtoY3dsdng1Mnh1Ym9wMGgydzF5c295aWQ0OTBocDdqNGIxbDFndCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ziNUOin6TC30HRQVHk/giphy.gif"