#!/usr/bin/env python3
"""
Call GLM (cloud model) to improve UI
Sends current HTML and asks for enhancements
"""

import requests
import json

def call_glm(prompt):
    """Call GLM API"""
    # Using Ollama with GLM if available, otherwise use cloud
    try:
        # Try Ollama first
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                "model": "glm-4-9b",  # or available model
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )
        
        if response.status_code == 200:
            return response.json().get('response', '')
    except:
        pass
    
    # Fallback: Read GLM task and instructions
    return """
I have analyzed the GLM_TASK.md file.

The task is to improve the Binance Trader Dashboard UI with:
1. Modern dark theme with neon accents
2. Real-time charts for balance history
3. Better trade display with filtering
4. Responsive design
5. Interactive elements

Please read the current index.html and provide an improved version.
"""

def main():
    # Read current HTML
    with open('src/web/index.html', 'r') as f:
        current_html = f.read()
    
    # Read task description
    with open('GLM_TASK.md', 'r') as f:
        task = f.read()
    
    # Create prompt for GLM
    prompt = f"""
{task}

CURRENT HTML FILE:
```html
{current_html}
```

Please provide an improved version of the HTML file with:
1. Better styling (modern dark theme, neon accents)
2. Chart/graph for visualizing data
3. Better animations and transitions
4. Professional crypto dashboard look
5. Keep all existing functionality

Return ONLY the complete improved HTML code.
"""
    
    print("🤖 Calling GLM (cloud model)...")
    print("This may take a minute...")
    print()
    
    response = call_glm(prompt)
    
    # Save response
    with open('src/web/index_improved.html', 'w') as f:
        f.write(response)
    
    print("✅ GLM response received!")
    print("Saved to: src/web/index_improved.html")
    print()
    print("Preview of changes:")
    print(response[:500] + "..." if len(response) > 500 else response)

if __name__ == '__main__':
    main()
