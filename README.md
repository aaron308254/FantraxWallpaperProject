# Fantrax Wallpaper Project for NBA Weekly Points League
<img width="1920" height="1080" alt="fantasy_wallpaper" src="https://github.com/user-attachments/assets/6429fed3-3c8d-4885-be9a-22f47a755b6f" />

A custom Python implementation for interacting with and building Wallpapers from Fantrax NBA league data. This project includes specific stability patches for the `fantraxapi` library to handle initialization errors and data inconsistencies.

## 🚀 Features
* Automated league data retrieval.
* Wallpaper building showing real-time Fantrax weekly period scores.
* **Custom Patches:** Includes runtime fixes for `Roster` and `League` objects within the `fantraxapi` package.
* **Environment Ready:** Fully configured with `venv` support and dependency tracking.

## 🛠️ Installation & Setup

**Clone the repository:**
```
git clone https://github.com/aaron308254/FantraxWallpaperProject.git
cd FantraxWallpaperProject
```
**Create a virtual environment:**
```
python -m venv .venv
```
**Activate the environment:**

Windows: 
```
.venv\Scripts\activate
```
Mac/Linux:
```
source .venv/bin/activate
```
**Install dependencies:**

```
pip install -r requirements.txt
```
## 🔧 Applied Monkey Patches
This project implements "Monkey Patching" to fix issues in the fantraxapi library without modifying the source files in your local environment.
The unofficial FantraxAPI was made for the NHL fantasy app and seems to have been made for a daily points league. Since the league I am a part of is a Weekly NBA points league,
the way that periods were assigned to dates had to be modified. After the patch, instead of periods being day-by-day they are week-by-week.

Roster.__init__: Overridden to bypass a super() initialization error and fixed period_date assignment to be the first date of a weekly period.

League.reset_info: Patched to allow for custom data resetting logic, assigning each scoring date to a certain period.

These patches are applied at the top of main.py and only exist in memory during execution.

## 📝 Usage
Ensure your league is publicly viewable. In the fantrax app, this can be toggled on by going to Commisioner -> League Setup -> Misc -> Misc -> Allow public to view league

Ensure your credentials are set up (league_id and myTeamID), then run:

```
python main.py
```

## ⏰ Running Automatically on Windows Startup (Task Scheduler)

To have the wallpaper script launch automatically whenever you log into Windows, without needing to open a terminal or VSCode, you can set it up as a scheduled task.

**1. Open Task Scheduler**

Press `Win + R`, type `taskschd.msc`, and press Enter.

**2. Create a New Task**

In the right-hand panel, click **Create Task** (not "Create Basic Task" — this gives you access to all settings upfront).

**3. Set the Trigger**

Go to the **Triggers** tab → click **New**.
- Set **Begin the task** to `At log on`
- Optionally check **Delay task for** and set it to `30 seconds` to give your network time to fully initialize before the script runs
- Click OK

**4. Set the Action**

Go to the **Actions** tab → click **New** → set **Action** to `Start a program`, then fill in the three fields:

| Field | Value |
|---|---|
| Program/script | `C:\Users\YourName\FantraxWallpaperProject\.venv\Scripts\pythonw.exe` |
| Add arguments | `Main.py` |
| Start in | `C:\Users\YourName\FantraxWallpaperProject` |

> **Note:** Use `pythonw.exe` instead of `python.exe` so the script runs silently in the background with no terminal window. Make sure the paths match your actual install location.

**5. Set Network Condition**

Go to the **Conditions** tab and under the **Network** section, check:
- ✅ **Start only if the following network connection is available** → set to `Any connection`

This ensures the script waits for an internet connection before attempting to fetch data from Fantrax.

**6. Save the Task**

Click **OK**. You may be prompted to enter your Windows password to save the task.

The script will now launch automatically every time you log in, refresh the wallpaper immediately, and continue updating every 5 minutes in the background. To verify it is running, open **Task Manager → Details** and look for `pythonw.exe`.
