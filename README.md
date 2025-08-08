# G-Code Pen Press Utility

A small Python/Tkinter GUI tool to automate inserting “pen-press” routines into your G-code files based on shape lengths. Instead of manually editing each file, just pick your parameters, set a distance threshold, and let the utility do the rest.

---

## Features

- **Pen-press parameters**  
  - **Pen Down Z** (default `5 mm`)  
  - **Pen Up Z** (default `10 mm`)  
  - **Drawing Height Z** (default `35 mm`)  

- **Pen-press XY position**  
  - Default `(X 5, Y 5)` — easily override to park your pen anywhere on the bed

- **Distance threshold slider**  
  - Only insert a full pen-press routine when the cumulative “drawing” length of shapes exceeds your chosen threshold (default `200 mm`)

- **Automatic shape parsing**  
  - Detects each pen-down segment (`M03 … G1 … G0`)  
  - Computes its total path length in millimeters  
  - Inserts a brief pen-lift (`M05 + G4 P450`) between **every** shape, plus a full pen-press routine when the threshold is exceeded

- **One-click file processing**  
  - Browse for any `.gcode` or `.gc` file  
  - Outputs a new file suffixed `_processed.gcode` in the same folder

---

## Requirements

- **Python 3.7+**  
- **Tkinter** (usually included with standard Python installations)  
- No other external libraries required

---

## Installation

1. **Clone or download** this repository.
2. (Optional) Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
