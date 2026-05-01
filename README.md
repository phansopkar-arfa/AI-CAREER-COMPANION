# AI Career Companion

AI Career Companion is a comprehensive platform designed to assist students and job seekers in their career journey using AI-powered tools.

## Features

- **Mock Interviews**: Practice interviews with AI-generated questions and real-time feedback.
- **Career Test**: Discover your strengths and suitable career paths.
- **Resume Builder**: Create professional resumes with AI assistance.
- **Career Coach**: Get personalized advice and guidance.
- **Student Dashboard**: Track your progress and history across all modules.

## Project Structure

- `accounts/`: User authentication and profile management.
- `mock_interview/`: AI-driven mock interview module.
- `student_career/`: Core logic for career assessment and tracking.
- `media/`: User-uploaded files (resumes, etc.).
- `static/`: Frontend assets (CSS, JS, images).

## Setup and Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/phansopkar-arfa/AI-CAREER-COMPANION.git
   cd AI-CAREER-COMPANION
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in the root directory and add your API keys (e.g., Groq, etc.).

4. **Run Migrations**:
   ```bash
   python manage.py migrate
   ```

5. **Start the Development Server**:
   ```bash
   python manage.py run_server
   ```

## Technologies Used

- **Backend**: Django (Python)
- **AI/LLM**: Integration with LLMs (e.g., Groq) for interview generation.
- **Frontend**: HTML5, Vanilla CSS, JavaScript.
- **Database**: SQLite (default) or PostgreSQL.

## License

[MIT License](LICENSE)
