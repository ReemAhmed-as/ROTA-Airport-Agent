const canvas = document.getElementById('mapCanvas');
const ctx = canvas.getContext('2d');
const container = document.getElementById('map-container');
const tooltip = document.getElementById('tooltip');
const ttTitle = document.getElementById('tt-title');
const ttCat = document.getElementById('tt-cat');

// --- Parse Target Info ---
const urlParams = new URLSearchParams(window.location.search);
const targetX = urlParams.has('x') ? parseFloat(urlParams.get('x')) : null;
const targetY = urlParams.has('y') ? parseFloat(urlParams.get('y')) : null;
const targetName = urlParams.get('name') || null;

// --- State ---
let locations = [];
let minX = 0, maxX = 0, minY = 0, maxY = 0;
let scale = 1, offsetX = 0, offsetY = 0;
let isDragging = false, startDragX = 0, startDragY = 0;
let hoveredLoc = null;
let currentFilter = 'all';

function getLocGroup(loc) {
    const sub = (loc.subcategory || "").toLowerCase();
    const cat = (loc.category || "").toLowerCase();
    const brand = (loc.brand || "").toLowerCase();
    
    if (sub.includes('gate') || cat.includes('gate') || brand.includes('gate') || brand.includes('بواب')) return 'gates';
    if (cat.includes('food') || cat.includes('beverage') || sub.includes('restaurant') || sub.includes('coffee') || sub.includes('cafe')) return 'food';
    if (cat.includes('retail') || cat.includes('shop') || sub.includes('retail')) return 'retail';
    return 'services';
}

const USER_LOCATION = { brand: "You are here - Gate 1", category: "Current Location", subcategory: "Origin", x: 0, y: 0 };

async function initMap() {
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();
    
    try {
        const res = await fetch('/api/locations');
        locations = await res.json();
    } catch(e) {
        console.error("Failed to load locations:", e);
        return;
    }
    
    if(locations.length > 0) {
        minX = Math.min(...locations.map(l => l.x), 0);
        maxX = Math.max(...locations.map(l => l.x), 0);
        minY = Math.min(...locations.map(l => l.y), 0);
        maxY = Math.max(...locations.map(l => l.y), 0);
    }
    
    // Padding
    const pad = 20;
    minX -= pad; maxX += pad; minY -= pad; maxY += pad;
    
    resetView();
    setupEvents();
    draw();
}

function resizeCanvas() {
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    draw();
}

function resetView() {
    const rangeX = maxX - minX || 100;
    const rangeY = maxY - minY || 100;
    
    const scaleX = canvas.width / rangeX;
    const scaleY = canvas.height / rangeY;
    scale = Math.min(scaleX, scaleY) * 0.9;
    
    if (targetX !== null && targetY !== null) {
        // Automatically focus on the path from user to target
        const rX = Math.max(Math.abs(targetX), 20) * 2.5;
        const rY = Math.max(Math.abs(targetY), 20) * 2.5;
        scale = Math.min(canvas.width / rX, canvas.height / rY) * 0.8;
        offsetX = canvas.width / 2 - (targetX / 2) * scale;
        offsetY = canvas.height / 2 - (targetY / 2) * scale;
    } else {
        offsetX = canvas.width / 2 - ((minX + maxX) / 2) * scale;
        offsetY = canvas.height / 2 - ((minY + maxY) / 2) * scale;
    }
    
    draw();
}

function worldToScreen(wx, wy) {
    return { x: wx * scale + offsetX, y: wy * scale + offsetY };
}

function screenToWorld(sx, sy) {
    return { x: (sx - offsetX) / scale, y: (sy - offsetY) / scale };
}

function draw() {
    if(!ctx) return;
    
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // --- Grid ---
    ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
    ctx.lineWidth = 1;
    const gridSpacing = 50 * scale;
    const offsetRemX = offsetX % gridSpacing;
    const offsetRemY = offsetY % gridSpacing;
    
    ctx.beginPath();
    for(let x = offsetRemX; x < canvas.width; x += gridSpacing) {
        ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height);
    }
    for(let y = offsetRemY; y < canvas.height; y += gridSpacing) {
        ctx.moveTo(0, y); ctx.lineTo(canvas.width, y);
    }
    ctx.stroke();

    // --- Main Axes ---
    const origin = worldToScreen(0,0);
    ctx.strokeStyle = "rgba(124,58,237,0.2)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(origin.x, 0); ctx.lineTo(origin.x, canvas.height);
    ctx.moveTo(0, origin.y); ctx.lineTo(canvas.width, origin.y);
    ctx.stroke();

    // --- Locations ---
    const hasTarget = targetX !== null && targetY !== null;
    
    locations.forEach(loc => {
        const grp = getLocGroup(loc);
        if (currentFilter !== 'all' && grp !== currentFilter) {
            return; // Skip rendering if filtered out
        }

        const isTarget = hasTarget && Math.abs(loc.x - targetX) < 1 && Math.abs(loc.y - targetY) < 1;
        const sc = worldToScreen(loc.x, loc.y);
        const isHovered = hoveredLoc === loc;
        
        let opacity = 1.0;
        if (hasTarget && !isTarget && !isHovered) {
            opacity = 0.15; // Dim non-target locations (Focus Mode)
        }

        let baseColor = "#7C3AED"; // Default purple
        if (grp === 'gates') baseColor = "#f59e0b"; // Amber
        else if (grp === 'food') baseColor = "#ef4444"; // Red
        else if (grp === 'retail') baseColor = "#3b82f6"; // Blue
        else if (grp === 'services') baseColor = "#10b981"; // Green
        
        ctx.globalAlpha = opacity;
        ctx.fillStyle = isHovered ? "#06b6d4" : baseColor;
        ctx.beginPath();
        ctx.arc(sc.x, sc.y, (isHovered || isTarget) ? 8 : 5, 0, Math.PI * 2);
        ctx.fill();
        
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1;
        ctx.stroke();
        ctx.globalAlpha = 1.0; // Reset alpha
    });
    
    // --- User Location marker ---
    const usc = worldToScreen(USER_LOCATION.x, USER_LOCATION.y);
    
    ctx.fillStyle = "rgba(34, 197, 94, 0.25)";
    ctx.beginPath();
    ctx.arc(usc.x, usc.y, 22, 0, Math.PI * 2);
    ctx.fill();

    ctx.fillStyle = "#22c55e"; 
    ctx.beginPath();
    ctx.arc(usc.x, usc.y, (hoveredLoc === USER_LOCATION) ? 12 : 9, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();

    ctx.fillStyle = "#000";
    ctx.font = "bold 13px Outfit, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("You (Gate 1)", usc.x, usc.y - 25);
    
    // --- Destination Path and Beacon ---
    if (targetX !== null && targetY !== null) {
        const t = worldToScreen(targetX, targetY);
        
        // Path line
        ctx.strokeStyle = "#06b6d4";
        ctx.lineWidth = 3;
        ctx.setLineDash([8, 8]);
        ctx.lineDashOffset = -(Date.now() / 40) % 16;
        ctx.beginPath();
        ctx.moveTo(usc.x, usc.y);
        ctx.lineTo(t.x, t.y);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Highlight Beacon
        ctx.fillStyle = "rgba(6, 182, 212, 0.4)";
        ctx.beginPath();
        ctx.arc(t.x, t.y, 18 + Math.sin(Date.now()/200)*4, 0, Math.PI * 2);
        ctx.fill();
        
        // Target Text
        ctx.fillStyle = "#000";
        ctx.font = "bold 14px Outfit, sans-serif";
        ctx.fillText(targetName || "Target", t.x, t.y - 30);
        
        if (!isDragging) {
            requestAnimationFrame(draw);
        }
    }
}

// --- Interaction Events ---
function setupEvents() {
    canvas.addEventListener('mousedown', e => {
        isDragging = true;
        startDragX = e.clientX - offsetX;
        startDragY = e.clientY - offsetY;
        canvas.style.cursor = 'grabbing';
    });
    
    window.addEventListener('mouseup', () => {
        isDragging = false;
        canvas.style.cursor = 'default';
        if(targetX !== null && targetY !== null) draw(); // retrigger animation loop if needed
    });
    
    canvas.addEventListener('mousemove', e => {
        if(isDragging) {
            offsetX = e.clientX - startDragX;
            offsetY = e.clientY - startDragY;
            draw();
            tooltip.style.display = 'none';
        } else {
            const rect = canvas.getBoundingClientRect();
            const mx = e.clientX - rect.left;
            const my = e.clientY - rect.top;
            
            let found = null;
            const usc = worldToScreen(USER_LOCATION.x, USER_LOCATION.y);
            const udX = mx - usc.x;
            const udY = my - usc.y;
            
            if(Math.sqrt(udX*udX + udY*udY) < 15) {
                found = USER_LOCATION;
            } else {
                for(let i = locations.length - 1; i >= 0; i--) {
                    const loc = locations[i];
                    const sc = worldToScreen(loc.x, loc.y);
                    const dX = mx - sc.x;
                    const dY = my - sc.y;
                    if(Math.sqrt(dX*dX + dY*dY) < 10) {
                        found = loc;
                        break;
                    }
                }
            }
            
            if(found !== hoveredLoc) {
                hoveredLoc = found;
                draw();
            }
            
            if(found) {
                tooltip.style.display = 'block';
                tooltip.style.left = mx + 'px';
                tooltip.style.top = my + 'px';
                ttTitle.innerText = found.brand || "Unknown";
                ttCat.innerText = found.category ? `${found.category} - ${found.subcategory}` : "Position: Origin";
            } else {
                tooltip.style.display = 'none';
            }
        }
    });

    canvas.addEventListener('wheel', e => {
        e.preventDefault();
        const zoomIntensity = 0.15;
        const wheel = e.deltaY < 0 ? 1 : -1;
        
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const worldPos = screenToWorld(mx, my);
        
        let newScale = scale * Math.exp(wheel * zoomIntensity);
        newScale = Math.max(0.1, Math.min(newScale, 50));
        
        scale = newScale;
        offsetX = mx - worldPos.x * scale;
        offsetY = my - worldPos.y * scale;
        
        draw();
    });

    document.getElementById('zoom-in').addEventListener('click', () => { scale *= 1.3; draw(); });
    document.getElementById('zoom-out').addEventListener('click', () => { scale /= 1.3; draw(); });
    document.getElementById('reset-view').addEventListener('click', resetView);

    // Filter Buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.getAttribute('data-filter');
            draw();
        });
    });
}

// Start
initMap();
