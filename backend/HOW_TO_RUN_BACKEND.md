# 🚀 How to Run MedAid Backend

## ⚠️ **Problem**
You're getting `ModuleNotFoundError: No module named 'medaid.settings'` because you're using the wrong virtual environment (`full-stack` instead of `venv`).

---

## ✅ **Solution - 3 Easy Ways**

### **Method 1: Use the Startup Script (Easiest)**

From the `backend` directory, run:

**PowerShell:**
```powershell
.\start_backend.ps1
```

**Command Prompt:**
```cmd
start_backend.bat
```

### **Method 2: Manual Commands**

```powershell
cd medaid
..\..\venv\Scripts\Activate.ps1
python manage.py runserver
```

### **Method 3: One-Liner**

From `backend` directory:
```powershell
cd medaid; ..\..\venv\Scripts\Activate.ps1; python manage.py runserver
```

---

## 📋 **Step-by-Step (If Above Doesn't Work)**

1. **Navigate to backend/medaid:**
   ```powershell
   cd d:\medaid-full stack\backend\medaid
   ```

2. **Activate the CORRECT virtual environment:**
   ```powershell
   ..\..\venv\Scripts\Activate.ps1
   ```
   
   You should see `(venv)` in your prompt, NOT `(full-stack)`

3. **Run the server:**
   ```powershell
   python manage.py runserver
   ```

4. **Success!** You should see:
   ```
   Starting development server at http://127.0.0.1:8000/
   ```

---

## 🔍 **How to Know You're Using the Right Environment**

**✅ Correct:**
```
(venv) PS D:\medaid-full stack\backend\medaid>
```

**❌ Wrong:**
```
(full-stack) PS D:\medaid-full stack\backend>
```

---

## 🆘 **Troubleshooting**

### **Issue: "full-stack environment is active"**
**Solution:** Deactivate it first:
```powershell
deactivate
```
Then follow Method 1 or 2 above.

### **Issue: "venv not found"**
**Solution:** Make sure you're in the `backend/medaid` directory, and the venv is at `backend/venv`.

### **Issue: "Permission denied"**
**Solution:** Run PowerShell as Administrator or use:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

## 📁 **Directory Structure**

```
d:\medaid-full stack\
├── backend/
│   ├── venv/              ← Correct virtual environment
│   ├── full-stack/        ← Wrong virtual environment (ignore this)
│   ├── medaid/            ← Django project (run server from here)
│   │   ├── manage.py
│   │   └── ...
│   ├── start_backend.ps1  ← Use this!
│   └── start_backend.bat  ← Or this!
└── frontend/
```

---

## ✅ **Quick Check**

After activating venv, run:
```powershell
python -c "import django; print(django.get_version())"
```

Should show Django version without errors.

---

## 🎯 **Summary**

**The problem:** You're in `backend` directory with `full-stack` environment  
**The solution:** Go to `backend/medaid` directory with `venv` environment

**Easiest way:**
```powershell
cd d:\medaid-full stack\backend
.\start_backend.ps1
```

**Done!** 🚀
