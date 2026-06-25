# NBS_Basebot

Selenium bots that review NBS disease-surveillance cases (COVID, iGAS, Hep B/C,
Gonorrhea, and more).

**New here? Start with the guide:**
[documentation/BOT_STATUS_AND_HOWTO.md](documentation/BOT_STATUS_AND_HOWTO.md) —
what each bot does, how to run them, and how the shared-session / retry features work.

Quick start:
```powershell
.\env\Scripts\Activate.ps1
python start_bots.py
```
Pick bots from the menu (space-separated numbers, in run order), enter your SOM
username and RSA passcode. The suite runs each selected bot's queue once, then stops.
