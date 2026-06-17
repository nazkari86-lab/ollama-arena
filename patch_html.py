import re

path = '/Users/dulatnurlanuly/ollama-arena/templates/index.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Inject ThreeJS dependencies
dep_block = """<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/EffectComposer.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/RenderPass.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/ShaderPass.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/CopyShader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/shaders/LuminosityHighPassShader.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/postprocessing/UnrealBloomPass.js"></script>
<script src="/static/arena3d.js"></script>"""
html = html.replace('<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>', dep_block)

# 2. Update Canvas to Div
canvas_old = """<canvas id="arena-canvas" style="width:100%; height:250px; background:#0d1117; display:block; border-radius:8px; image-rendering:pixelated;"></canvas>"""
canvas_new = """<div id="arena-3d-container" style="width:100%; height:350px; background:#05080f; border-radius:8px; overflow:hidden; position:relative;"></div>"""
html = html.replace(canvas_old, canvas_new)

# 3. Remove PixelArena Class
start_str = "// ── PIXEL ARENA CLASS ──────"
end_str = "// Tabs"
if start_str in html and end_str in html:
    before = html.split(start_str)[0]
    after = end_str + html.split(end_str)[1]
    html = before + after

# 4. Update instantiation in runMatch
html = html.replace("window.arenaVisualizer = new PixelArena('arena-canvas', ma, mb, n);", 
                    "if(window.arenaVisualizer) window.arenaVisualizer.destroy(); window.arenaVisualizer = new ThreeJSArena('arena-3d-container', ma, mb, n);")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
    
print("Updated index.html successfully.")
