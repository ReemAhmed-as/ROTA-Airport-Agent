const messagesContainer = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const newChatBtn = document.getElementById('new-chat-btn');

let lastUserIsAr = false;

// --- History Management ---
function saveHistory() {
    // Don't save if typing indicator is active (prevents stuck dots on reload)
    if (!document.getElementById('typing-indicator')) {
        sessionStorage.setItem('rota_chat_history', messagesContainer.innerHTML);
    }
}

function loadHistory() {
    const history = sessionStorage.getItem('rota_chat_history');
    if (history) {
        messagesContainer.innerHTML = history;
        messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
    }
}

// Load history immediately on script run
loadHistory();

// --- Helpers ---
function isArabic(text) {
    return /[\u0600-\u06FF]/.test(text);
}

function getBrandIcon(desc) {
    const d = (desc || '').toLowerCase();
    if (d.includes('coffee') || d.includes('café') || d.includes('قهوة')) return 'fa-mug-hot';
    if (d.includes('burger') || d.includes('chicken') || d.includes('دجاج')) return 'fa-burger';
    if (d.includes('sandwich') || d.includes('ساندويتش')) return 'fa-bread-slice';
    if (d.includes('book') || d.includes('magazine') || d.includes('كتاب')) return 'fa-book';
    if (d.includes('pharmacy') || d.includes('صيدل')) return 'fa-pills';
    if (d.includes('car') || d.includes('taxi') || d.includes('سيارة')) return 'fa-car';
    if (d.includes('vending') || d.includes('آلة')) return 'fa-box';
    if (d.includes('donut') || d.includes('بيك') || d.includes('bun')) return 'fa-cookie';
    return 'fa-store';
}

function getCardContent(b, isAr) {
    const fullDesc = typeof b === 'object' ? (b.content || '') : '';
    const arMatch = fullDesc.match(/\(([^)]+)\)/);
    const enPart = fullDesc.split('(')[0].trim();
    return isAr ? (arMatch ? arMatch[1] : fullDesc) : (enPart || fullDesc);
}

// --- DOM Manipulation ---
function addMessage(text, role, isHtml = false, forceAr = null) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role} slide-in`;
    const icon = role === 'assistant' ? 'fa-robot' : 'fa-user';
    const contentHtml = isHtml ? text : text.replace(/\n/g, '<br>');

    // Determine direction
    let dir = '';
    if (isHtml) {
        dir = forceAr ? 'dir="rtl"' : 'dir="ltr"';
    } else {
        dir = isArabic(text) ? 'dir="rtl"' : '';
    }

    msgDiv.innerHTML = `
        <div class="avatar"><i class="fa-solid ${icon}"></i></div>
        <div class="message-content" ${dir}>${contentHtml}</div>
    `;
    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
    
    saveHistory();
}

function showTyping() {
    const div = document.createElement('div');
    div.className = 'message assistant slide-in';
    div.id = 'typing-indicator';
    div.innerHTML = `
        <div class="avatar"><i class="fa-solid fa-robot"></i></div>
        <div class="message-content typing-indicator">
            <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
        </div>`;
    messagesContainer.appendChild(div);
    messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
}

function removeTyping() {
    document.getElementById('typing-indicator')?.remove();
    saveHistory();
}

// --- Card Generation ---
function metersAndTime(distanceUnits) {
    // Grid: X/Y range -999 to +999 → 2000 units total span
    // Typical airport terminal ~500m long → 1 unit ≈ 0.25 metres
    const UNIT_TO_METRES = 0.25;
    const WALK_SPEED_MPM = 83;   // 5 km/h = 83 m/min average walking
    const meters = Math.round(distanceUnits * UNIT_TO_METRES);
    const mins   = Math.max(1, Math.ceil(meters / WALK_SPEED_MPM));
    return { meters, mins };
}

function createCardHTML(b, index, isAr, type) {
    const brandName = typeof b === 'object' ? b.name : b;
    const cleanName = brandName.replace(/ \((Recommendation|توصية|closest|الأقرب)\)/g, '').trim();
    const icon      = getBrandIcon(brandName);
    const cardDir   = isAr ? 'rtl' : 'ltr';
    const cardId    = `card-${type.charAt(0)}-${Date.now()}-${index}`;

    const mapHref    = b.x !== undefined
        ? `/map?x=${b.x}&y=${b.y}&name=${encodeURIComponent(cleanName).replace(/'/g, "%27")}`
        : '#';
    const onclickStr = `onclick="window.location.href='${mapHref}'"` ;

    // Distance & time row
    let distHtml = '';
    if (typeof b === 'object' && b.distance !== undefined) {
        const { meters, mins } = metersAndTime(b.distance);
        if (isAr) {
            distHtml = `
                <div class="card-meta-row">
                    <span class="card-meta-item">
                        <i class="fa-solid fa-location-dot"></i>
                        ${meters} م
                    </span>
                    <span class="card-meta-item">
                        <i class="fa-solid fa-person-walking"></i>
                        ~${mins} دقيقة
                    </span>
                </div>`;
        } else {
            distHtml = `
                <div class="card-meta-row">
                    <span class="card-meta-item">
                        <i class="fa-solid fa-location-dot"></i>
                        ${meters} m
                    </span>
                    <span class="card-meta-item">
                        <i class="fa-solid fa-person-walking"></i>
                        ~${mins} min
                    </span>
                </div>`;
        }
    }

    // Recommendation card (horizontal compact)
    if (type === 'recommendation') {
        return `
            <div class="rec-card" id="${cardId}" dir="${cardDir}" ${onclickStr}>
                <div class="rec-icon"><i class="fa-solid ${icon}"></i></div>
                <div class="rec-details">
                    <div class="rec-title" title="${cleanName}">${cleanName}</div>
                    ${distHtml}
                </div>
            </div>`;
    }

    // Closest / regular card
    const extraClass = type === 'closest' ? 'brand-card-closest' : '';
    return `
        <div class="brand-card ${extraClass}" id="${cardId}" dir="${cardDir}" ${onclickStr}>
            <div class="brand-header">
                <div class="brand-icon"><i class="fa-solid ${icon}"></i></div>
                <div class="brand-title">${cleanName}</div>
            </div>
            ${distHtml}
        </div>`;
}

// --- Main Chat Logic ---
async function sendMessage(manualText = null) {
    const text = manualText || userInput.value.trim();
    if (!text) return;

    lastUserIsAr = isArabic(text);
    addMessage(text, 'user');
    userInput.value = '';
    showTyping();

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const data = await response.json();
        removeTyping();

        if (data.error) return addMessage(data.error, 'assistant');

        if (data.message) {
            const msgDir = lastUserIsAr ? 'dir="rtl"' : 'dir="ltr"';
            let content = `<p style="font-weight:600;margin-bottom:4px" ${msgDir}>${data.message}</p>`;

            if (data.brands && data.brands.length > 0) {
                const closest = data.brands.filter(b => b.type === "closest");
                const recs    = data.brands.filter(b => b.type === "recommendation");
                const regular = data.brands.filter(b => b.type === "regular" || !b.type);

                const listDir = lastUserIsAr ? ' dir="rtl"' : '';

                if (closest.length) {
                    content += `<div class="brand-list"${listDir}>`;
                    closest.forEach((b, i) => content += createCardHTML(b, i, lastUserIsAr, 'closest'));
                    content += '</div>';
                }

                if (regular.length) {
                    content += `<div class="brand-list"${listDir}>`;
                    regular.forEach((b, i) => content += createCardHTML(b, i, lastUserIsAr, 'regular'));
                    content += '</div>';
                }

                if (recs.length) {
                    content += `<div class="recommendations-row"${listDir}>`;
                    recs.forEach((b, i) => content += createCardHTML(b, i, lastUserIsAr, 'recommendation'));
                    content += '</div>';
                }
            }
            addMessage(content, 'assistant', true, lastUserIsAr);
        } else {
            addMessage(lastUserIsAr ? 'عفواً، لم أتمكن من معالجة طلبك.' : 'Sorry, I could not process your request.', 'assistant');
        }
    } catch (err) {
        removeTyping();
        addMessage(lastUserIsAr ? 'حدث خطأ في الاتصال. يرجى المحاولة لاحقاً.' : 'Connection error. Please try again.', 'assistant');
        console.error(err);
    }
}

// --- Event Listeners ---
sendBtn.addEventListener('click', () => sendMessage());
userInput.addEventListener('keypress', e => e.key === 'Enter' && sendMessage());

newChatBtn.addEventListener('click', () => {
    messagesContainer.innerHTML = '';
    addMessage('مرحبًا انا روتا ايجنت مساعدك الذكي في مطار الملك خالد', 'assistant');
});
