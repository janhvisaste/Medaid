import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GOOGLE_API_KEY")

if not key:
    print("Error: No API key found")
    exit(1)

print(f"Testing key: {key[:5]}...{key[-5:]}")

genai.configure(api_key=key)

print("Listing available models...")
try:
    found_models = []
    print("Found models:")
    for m in genai.list_models():
        print(f" - {m.name} ({m.supported_generation_methods})")
        if 'generateContent' in m.supported_generation_methods:
            found_models.append(m.name)
            
    if not found_models:
        print("WARNING: No models found with 'generateContent' capability.")
    else:
        print(f"Available generative models: {found_models}")
        
        # Try finding a suitable model
        target_model = 'models/gemini-1.5-flash'
        if target_model not in found_models:
            if 'models/gemini-pro' in found_models:
                target_model = 'models/gemini-pro'
            elif found_models:
                target_model = found_models[0]
        
        print(f"Attempting generation with '{target_model}'...")
        model = genai.GenerativeModel(target_model)
        response = model.generate_content("Hello")
        print(f"SUCCESS! Response: {response.text}")

except Exception as e:
    print(f"API Error: {e}")
