# CLAUDE.md - Conquest Project Context

## Project Overview
- **Project Name:** Conquest
- **Tagline:** Learn. Compete. Conquer.
- **Description:** A competitive strategy game for students to learn through territory conquest. An AI system analyzes course study materials (PDFs, presentations, notes) and generates questions, answers, and difficulty levels for the game.

## Tech Stack
- **Language:** Python
- **UI Framework:** Streamlit
- **Version Control:** Git / GitHub

## Data & AI
- **Data Source:** Study materials uploaded by users (PDFs, text documents, presentations).
- **AI Role:** The AI extracts text, identifies key concepts, and generates structured learning questions (question, multiple-choice options, correct answer, explanation, difficulty level).
- **Note for M1:** Since users upload materials dynamically, the initial phase focuses on handling file uploads and displaying sample data/questions.

## Project Structure
- `app.py`: Main Streamlit application entry point.
- `requirements.txt`: Python dependencies (e.g., streamlit, pandas).
- `data/`: Folder containing sample datasets or uploaded study materials.
- `README.md`: Full project definition and user stories.
