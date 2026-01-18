@echo off
echo Starting MedAid Backend Server...
cd medaid
call ..\..\venv\Scripts\activate.bat
python manage.py runserver
