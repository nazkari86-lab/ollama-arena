import re

path = '/Users/dulatnurlanuly/ollama-arena/templates/index.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

# Replace charA -> modelA.userData and charB -> modelB.userData
html = html.replace("window.arenaVisualizer.charA.state", "window.arenaVisualizer.modelA.userData.state")
html = html.replace("window.arenaVisualizer.charB.state", "window.arenaVisualizer.modelB.userData.state")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
    
print("Updated charA/charB to modelA/B.userData successfully.")
