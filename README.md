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
