class ThreeJSArena {
  constructor(containerId, nameA, nameB, totalRounds = 5) {
    this.container = document.getElementById(containerId);
    
    // Ensure we have dimensions
    const rect = this.container.getBoundingClientRect();
    this.width = rect.width || this.container.offsetWidth || 800;
    this.height = rect.height || this.container.offsetHeight || 450;
    
    this.totalRounds = totalRounds;
    this.nameA = nameA;
    this.nameB = nameB;

    this.active = true;
    this.particles = [];
    this.lasers = [];
    this.floatingTexts = [];
    this.clock = new THREE.Clock();
    
    this.initThreeJS();
    this.createEnvironment();
    this.createModels();
    
    this.onWindowResize = this.onWindowResize.bind(this);
    window.addEventListener('resize', this.onWindowResize);

    this.loop = this.loop.bind(this);
    requestAnimationFrame(this.loop);

    // Overlay for floating DOM text
    this.overlay = document.createElement('div');
    this.overlay.style.position = 'absolute';
    this.overlay.style.top = '0';
    this.overlay.style.left = '0';
    this.overlay.style.width = '100%';
    this.overlay.style.height = '100%';
    this.overlay.style.pointerEvents = 'none';
    this.overlay.style.overflow = 'hidden';
    this.container.appendChild(this.overlay);

    this.cameraAnimTime = 0;
  }

  createGlowTexture(colorStr) {
    const canvas = document.createElement('canvas');
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    gradient.addColorStop(0, colorStr);
    gradient.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 64, 64);
    const tex = new THREE.CanvasTexture(canvas);
    return tex;
  }

  initThreeJS() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x05080f);
    this.scene.fog = new THREE.FogExp2(0x05080f, 0.015);

    this.camera = new THREE.PerspectiveCamera(50, this.width / this.height, 0.1, 1000);
    this.camera.position.set(0, 20, 55);
    this.camera.lookAt(0, 5, 0);
    this.baseCameraPos = this.camera.position.clone();
    this.shakeIntensity = 0;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    this.renderer.setSize(this.width, this.height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.appendChild(this.renderer.domElement);

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);
    
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(10, 30, 20);
    this.scene.add(dirLight);
  }

  onWindowResize() {
    if (!this.container || !this.active) return;
    const rect = this.container.getBoundingClientRect();
    const newWidth = rect.width || this.container.offsetWidth;
    const newHeight = rect.height || this.container.offsetHeight;
    
    if (newWidth > 0 && newHeight > 0) {
      this.width = newWidth;
      this.height = newHeight;
      this.camera.aspect = this.width / this.height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(this.width, this.height);
    }
  }

  createEnvironment() {
    // Cyber Grid
    const gridHelper = new THREE.GridHelper(150, 60, 0x1f6feb, 0x0d1117);
    gridHelper.position.y = 0;
    this.scene.add(gridHelper);

    // Floor Plate
    const floorGeo = new THREE.PlaneGeometry(150, 150);
    const floorMat = new THREE.MeshStandardMaterial({ color: 0x03050a, roughness: 0.8, metalness: 0.2 });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -0.1;
    this.scene.add(floor);
  }

  buildDrone(colorHex, isLeft) {
    const group = new THREE.Group();
    
    // Core geometry
    const coreGeo = new THREE.OctahedronGeometry(2, 1);
    const coreMat = new THREE.MeshStandardMaterial({ 
      color: colorHex, 
      wireframe: true,
      emissive: colorHex,
      emissiveIntensity: 0.8,
      transparent: true,
      opacity: 0.9
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    core.position.y = 8;
    group.add(core);

    // Inner glowing sphere
    const innerGeo = new THREE.SphereGeometry(1.2, 16, 16);
    const innerMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
    const inner = new THREE.Mesh(innerGeo, innerMat);
    inner.position.y = 8;
    group.add(inner);

    // Additive Glow Sprite
    const colorStr = '#' + colorHex.toString(16).padStart(6, '0');
    const glowTex = this.createGlowTexture(colorStr);
    const glowMat = new THREE.SpriteMaterial({ 
      map: glowTex, 
      color: colorHex, 
      transparent: true, 
      blending: THREE.AdditiveBlending,
      depthWrite: false
    });
    const glow = new THREE.Sprite(glowMat);
    glow.scale.set(18, 18, 1);
    glow.position.y = 8;
    group.add(glow);

    // Orbiting rings
    const rings = [];
    for(let i=0; i<3; i++) {
      const rGeo = new THREE.TorusGeometry(3.5 + i*0.5, 0.05, 16, 64);
      const rMat = new THREE.MeshStandardMaterial({ color: colorHex, emissive: colorHex, emissiveIntensity: 0.4, transparent: true, opacity: 0.6 });
      const r = new THREE.Mesh(rGeo, rMat);
      r.position.y = 8;
      group.add(r);
      rings.push({ mesh: r, speed: (Math.random() - 0.5) * 4 });
    }

    group.position.x = isLeft ? -20 : 20;
    group.userData = {
      baseX: group.position.x,
      state: "idle",
      color: colorHex,
      colorStr: colorStr,
      animTime: Math.random() * 10,
      core: core,
      inner: inner,
      rings: rings,
      glow: glow
    };
    
    return group;
  }

  createModels() {
    this.modelA = this.buildDrone(0x58a6ff, true);
    this.scene.add(this.modelA);

    this.modelB = this.buildDrone(0xff7b72, false);
    this.scene.add(this.modelB);

    this.addNameTag(this.nameA, this.modelA);
    this.addNameTag(this.nameB, this.modelB);
  }

  addNameTag(name, model) {
    const div = document.createElement('div');
    div.textContent = name;
    div.style.position = 'absolute';
    div.style.color = '#fff';
    div.style.fontFamily = "'JetBrains Mono', monospace";
    div.style.fontSize = '12px';
    div.style.fontWeight = '600';
    div.style.textShadow = `0 0 10px ${model.userData.colorStr}`;
    div.style.background = 'rgba(13, 17, 23, 0.7)';
    div.style.padding = '4px 10px';
    div.style.borderRadius = '4px';
    div.style.border = `1px solid ${model.userData.colorStr}`;
    div.style.pointerEvents = 'none';
    div.style.backdropFilter = 'blur(4px)';
    div.style.transition = 'transform 0.1s ease-out';
    this.overlay.appendChild(div);
    model.userData.nameTag = div;
  }

  updateNameTags() {
    [this.modelA, this.modelB].forEach(model => {
      const vec = new THREE.Vector3();
      vec.setFromMatrixPosition(model.userData.core.matrixWorld);
      vec.y += 6; // offset above drone
      vec.project(this.camera);
      const x = (vec.x * .5 + .5) * this.width;
      const y = (vec.y * -.5 + .5) * this.height;
      model.userData.nameTag.style.left = `${x}px`;
      model.userData.nameTag.style.top = `${y}px`;
      model.userData.nameTag.style.transform = 'translate(-50%, -50%)';
    });
  }

  triggerRound(outcome, scoreA, scoreB, taskId) {
    this.spawnFloatText(`+${scoreA.toFixed(1)}`, "#58a6ff", this.modelA);
    this.spawnFloatText(`+${scoreB.toFixed(1)}`, "#ff7b72", this.modelB);

    if (outcome === "a_wins") {
      this.shootLaser(this.modelA, this.modelB);
    } else if (outcome === "b_wins") {
      this.shootLaser(this.modelB, this.modelA);
    } else {
      this.shootLaser(this.modelA, null);
      this.shootLaser(this.modelB, null);
    }
  }

  shootLaser(attacker, target) {
    const start = new THREE.Vector3().setFromMatrixPosition(attacker.userData.core.matrixWorld);
    const end = target ? new THREE.Vector3().setFromMatrixPosition(target.userData.core.matrixWorld) : new THREE.Vector3(0, 8, 0);

    // Create Laser Beam
    const material = new THREE.LineBasicMaterial({ 
      color: attacker.userData.color,
      linewidth: 6,
      blending: THREE.AdditiveBlending,
      transparent: true
    });
    const geometry = new THREE.BufferGeometry().setFromPoints([start, end]);
    const line = new THREE.Line(geometry, material);
    this.scene.add(line);
    
    this.lasers.push({ mesh: line, life: 0.35 });
    
    // Attack animation
    attacker.userData.state = "attack";
    attacker.userData.animTime = 0;

    // Shake & Impact
    this.shakeIntensity = 0.6;
    this.spawnParticles(start, attacker.userData.color, 20);

    setTimeout(() => {
      if (!this.active) return;
      if (target) {
        this.spawnParticles(end, attacker.userData.color, 60);
        this.shakeIntensity = 1.5;
        target.userData.state = "hit";
        target.userData.animTime = 0;
      } else {
        this.spawnParticles(end, 0xffffff, 40);
      }
    }, 100);
  }

  spawnParticles(pos, color, count) {
    for(let i=0; i<count; i++) {
      const pMat = new THREE.MeshStandardMaterial({ 
        color: color, 
        emissive: color,
        emissiveIntensity: 0.8,
        transparent: true, 
        blending: THREE.AdditiveBlending 
      });
      const pGeo = new THREE.BoxGeometry(0.4, 0.4, 0.4);
      const p = new THREE.Mesh(pGeo, pMat);
      p.position.copy(pos);
      
      const speed = 15 + Math.random() * 25;
      const vel = new THREE.Vector3(
        (Math.random()-0.5),
        (Math.random()-0.5) + 0.5,
        (Math.random()-0.5)
      ).normalize().multiplyScalar(speed);
      
      const rotVel = new THREE.Vector3(
        (Math.random()-0.5)*10,
        (Math.random()-0.5)*10,
        (Math.random()-0.5)*10
      );

      this.particles.push({ mesh: p, vel: vel, rotVel: rotVel, life: 1.2 + Math.random()*0.8 });
      this.scene.add(p);
    }
  }

  spawnFloatText(text, color, model) {
    const div = document.createElement('div');
    div.textContent = text;
    div.style.position = 'absolute';
    div.style.color = color;
    div.style.fontFamily = "'JetBrains Mono', monospace";
    div.style.fontWeight = '800';
    div.style.fontSize = '24px';
    div.style.textShadow = `0 0 15px ${color}, 0 0 5px #fff`;
    div.style.pointerEvents = 'none';
    this.overlay.appendChild(div);
    this.floatingTexts.push({ el: div, model: model, life: 2.0, yOffset: 0 });
  }

  triggerEndGame(winner) {
    this.spawnParticles(new THREE.Vector3(0, 15, 0), 0xffffff, 250);
    this.shakeIntensity = 2.5;

    if (winner === "draw") {
      this.modelA.userData.state = "idle";
      this.modelB.userData.state = "idle";
    } else if (winner === this.nameA) {
      this.modelA.userData.state = "victory";
      this.modelB.userData.state = "defeated";
    } else {
      this.modelA.userData.state = "defeated";
      this.modelB.userData.state = "victory";
    }
  }

  loop() {
    if (!this.active) return;
    requestAnimationFrame(this.loop);
    
    // Safeguard against hidden container
    if (this.width === 0 || this.height === 0) {
      this.onWindowResize();
    }

    const dt = Math.min(this.clock.getDelta(), 0.1);

    // Dramatic Camera Sweep on Match Start
    if (this.cameraAnimTime < 3.0) {
      this.cameraAnimTime += dt;
      const t = Math.min(this.cameraAnimTime / 3.0, 1.0);
      const ease = 1 - Math.pow(1 - t, 4); // ease out quart
      
      const sweepX = Math.sin((1 - ease) * Math.PI * 0.5) * 60;
      const sweepY = 50 - ease * 30;
      const sweepZ = 120 - ease * 65;
      
      this.baseCameraPos.set(sweepX, sweepY, sweepZ);
      this.camera.position.copy(this.baseCameraPos);
      this.camera.lookAt(0, 5, 0);
    } else {
      this.baseCameraPos.set(0, 20, 55);
      if (this.shakeIntensity <= 0) {
        this.camera.position.copy(this.baseCameraPos);
        this.camera.lookAt(0, 5, 0);
      }
    }

    // Camera Shake Layer
    if (this.shakeIntensity > 0) {
      this.camera.position.x = this.baseCameraPos.x + (Math.random()-0.5)*this.shakeIntensity;
      this.camera.position.y = this.baseCameraPos.y + (Math.random()-0.5)*this.shakeIntensity;
      this.camera.position.z = this.baseCameraPos.z + (Math.random()-0.5)*this.shakeIntensity;
      this.shakeIntensity -= dt * 3.5;
      if (this.shakeIntensity < 0) this.shakeIntensity = 0;
    }

    // Update Models
    [this.modelA, this.modelB].forEach(m => {
      const d = m.userData;
      d.animTime += dt;
      
      if (d.state === "idle") {
        m.position.y = Math.sin(d.animTime * 2) * 2;
        d.core.rotation.x += dt;
        d.core.rotation.y += dt;
        d.rings.forEach(r => {
          r.mesh.rotation.x += dt * r.speed;
          r.mesh.rotation.y += dt * r.speed;
        });
      } else if (d.state === "attack") {
        const p = d.animTime / 0.3;
        if (p < 1) {
          m.position.x = THREE.MathUtils.lerp(d.baseX, d.baseX > 0 ? d.baseX - 4 : d.baseX + 4, Math.sin(p * Math.PI));
        } else {
          m.position.x = d.baseX;
          d.state = "idle";
        }
      } else if (d.state === "hit") {
        m.position.x = d.baseX + (Math.random() - 0.5) * 2.5;
        m.position.y = (Math.random() - 0.5) * 2.5;
        if (d.animTime > 0.4) d.state = "idle";
      } else if (d.state === "victory") {
        m.position.y = Math.sin(d.animTime * 5) * 3;
        d.core.rotation.x += dt * 5;
        d.core.rotation.y += dt * 5;
      } else if (d.state === "defeated") {
        m.position.y = -7; // drop to floor
        d.glow.material.opacity = 0;
      }
    });

    // Update Lasers
    for(let i=this.lasers.length-1; i>=0; i--) {
      const l = this.lasers[i];
      l.life -= dt;
      if (l.life <= 0) {
        this.scene.remove(l.mesh);
        this.lasers.splice(i, 1);
      } else {
        l.mesh.material.opacity = Math.max(0, l.life / 0.35);
      }
    }

    // Update Particles (with gravity and bounce)
    for(let i=this.particles.length-1; i>=0; i--) {
      const p = this.particles[i];
      p.life -= dt * 1.2;
      if (p.life <= 0) {
        this.scene.remove(p.mesh);
        this.particles.splice(i, 1);
      } else {
        p.vel.y -= 40 * dt; // Gravity
        p.mesh.position.addScaledVector(p.vel, dt);
        
        // Bounce on floor
        if (p.mesh.position.y < 0) {
          p.mesh.position.y = 0;
          p.vel.y *= -0.6; // bounce factor
          p.vel.x *= 0.8; // friction
          p.vel.z *= 0.8;
        }

        p.mesh.rotation.x += p.rotVel.x * dt;
        p.mesh.rotation.y += p.rotVel.y * dt;
        p.mesh.rotation.z += p.rotVel.z * dt;
        
        p.mesh.material.opacity = p.life;
        p.mesh.scale.setScalar(p.life);
      }
    }

    // Update Floating Texts
    for(let i=this.floatingTexts.length-1; i>=0; i--) {
      const t = this.floatingTexts[i];
      t.life -= dt;
      if (t.life <= 0) {
        t.el.remove();
        this.floatingTexts.splice(i, 1);
      } else {
        t.yOffset += dt * 50; // drift up
        const vec = new THREE.Vector3();
        vec.setFromMatrixPosition(t.model.userData.core.matrixWorld);
        vec.project(this.camera);
        const x = (vec.x * .5 + .5) * this.width;
        const y = (vec.y * -.5 + .5) * this.height - t.yOffset;
        t.el.style.left = `${x}px`;
        t.el.style.top = `${y}px`;
        t.el.style.opacity = t.life;
        const scale = 1 + (2 - t.life) * 0.1;
        t.el.style.transform = `translate(-50%, -50%) scale(${scale})`;
      }
    }

    this.updateNameTags();
    this.renderer.render(this.scene, this.camera);
  }

  destroy() {
    this.active = false;
    window.removeEventListener('resize', this.onWindowResize);
    this.overlay.remove();
    if (this.renderer) {
      this.renderer.dispose();
      if (this.container.contains(this.renderer.domElement)) {
        this.container.removeChild(this.renderer.domElement);
      }
    }
  }
}
