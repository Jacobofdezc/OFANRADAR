/**
 * OFANRADAR - Guided Onboarding Engine (Feature 26)
 * Interactive 4-Step Tooltip Tour for New Users
 */

const TOUR_STEPS = [
    {
        title: "1. Temperatura de Compra e Intent Score ⚡",
        description: "OFANRADAR calcula la temperatura de compra de cada empresa (0-100) en tiempo real mediante 5 vectores: Contrataciones, Expansión, Estrés Financiero, Crecimiento y Cambios de Tech Stack.",
        target: ".intent-score-badge, .stat-card, header"
    },
    {
        title: "2. Búsqueda y Filtros Avanzados 🔍",
        description: "Filtra la base de datos por industria, número de empleados, tipo de señal (BORME, Ofertas de Empleo, Certificados SSL/DNS) o puntuación de intención.",
        target: ".search-bar-container, #searchInput, input[type='search']"
    },
    {
        title: "3. Simulador de Señales Públicas en Vivo 🧪",
        description: "Prueba la inyección instantánea de eventos (ej: cambios en el Registro Mercantil o picos de contratación) y observa cómo la IA recalcula la puntuación inmediatamente.",
        target: "#signalSimulatorBtn, .simulator-card, #btnIngestSignal"
    },
    {
        title: "4. Exportación CSV y Alertas Push 🚀",
        description: "Exporta datos prioritarios a CSV con un clic o configura reglas de alertas automatizadas por Email o Webhook para recibir avisos cuando una empresa supere un umbral.",
        target: "#exportCsvBtn, #alertSubBtn, .action-buttons"
    }
];

class OnboardingTour {
    constructor() {
        this.currentStep = 0;
        this.isOpen = false;
    }

    init() {
        // Auto start if user hasn't completed onboarding yet
        const completed = localStorage.getItem("ofanradar_onboarding_completed");
        if (!completed) {
            setTimeout(() => this.startTour(), 1200);
        }
    }

    startTour() {
        this.currentStep = 0;
        this.isOpen = true;
        this.renderStep();
    }

    nextStep() {
        if (this.currentStep < TOUR_STEPS.length - 1) {
            this.currentStep++;
            this.renderStep();
        } else {
            this.completeTour();
        }
    }

    prevStep() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this.renderStep();
        }
    }

    completeTour() {
        localStorage.setItem("ofanradar_onboarding_completed", "true");
        this.closeTour();
    }

    closeTour() {
        this.isOpen = false;
        const overlay = document.getElementById("onboardingOverlay");
        if (overlay) {
            overlay.remove();
        }
    }

    renderStep() {
        let overlay = document.getElementById("onboardingOverlay");
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.id = "onboardingOverlay";
            overlay.className = "onboarding-overlay";
            document.body.appendChild(overlay);
        }

        const step = TOUR_STEPS[this.currentStep];
        const stepNum = this.currentStep + 1;
        const totalSteps = TOUR_STEPS.length;

        overlay.innerHTML = `
            <div class="onboarding-modal-card">
                <div class="onboarding-header">
                    <span class="onboarding-badge">Paso ${stepNum} de ${totalSteps}</span>
                    <button class="onboarding-close-btn" onclick="window.onboardingEngine.closeTour()">&times;</button>
                </div>
                <h3 class="onboarding-title">${step.title}</h3>
                <p class="onboarding-desc">${step.description}</p>
                <div class="onboarding-actions">
                    ${this.currentStep > 0 ? `<button class="btn-tour-sec" onclick="window.onboardingEngine.prevStep()">Anterior</button>` : '<div></div>'}
                    <div>
                        <button class="btn-tour-skip" onclick="window.onboardingEngine.completeTour()">Omitir</button>
                        <button class="btn-tour-pri" onclick="window.onboardingEngine.nextStep()">
                            ${this.currentStep === totalSteps - 1 ? '¡Comenzar!' : 'Siguiente'}
                        </button>
                    </div>
                </div>
            </div>
        `;
    }
}

// Inject onboarding styles dynamically
const style = document.createElement('style');
style.textContent = `
.onboarding-overlay {
    position: fixed;
    inset: 0;
    background: rgba(5, 11, 20, 0.75);
    backdrop-filter: blur(4px);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    animation: fadeIn 0.3s ease-out;
}

.onboarding-modal-card {
    background: #0f172a;
    border: 1px solid rgba(0, 229, 255, 0.3);
    box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6), 0 0 20px rgba(0, 229, 255, 0.15);
    border-radius: 16px;
    padding: 2rem;
    max-width: 480px;
    width: 90%;
    color: #f3f4f6;
}

.onboarding-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
}

.onboarding-badge {
    background: rgba(0, 229, 255, 0.1);
    color: #00e5ff;
    padding: 0.3rem 0.75rem;
    border-radius: 12px;
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
}

.onboarding-close-btn {
    background: none;
    border: none;
    color: #9ca3af;
    font-size: 1.5rem;
    cursor: pointer;
}

.onboarding-title {
    margin: 0 0 0.75rem 0;
    font-size: 1.35rem;
    font-weight: 700;
    color: #ffffff;
}

.onboarding-desc {
    color: #94a3b8;
    font-size: 0.95rem;
    line-height: 1.5;
    margin-bottom: 1.5rem;
}

.onboarding-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.btn-tour-pri {
    background: linear-gradient(135deg, #00e5ff 0%, #0077ff 100%);
    color: #050b14;
    font-weight: 700;
    border: none;
    padding: 0.6rem 1.25rem;
    border-radius: 8px;
    cursor: pointer;
}

.btn-tour-sec {
    background: rgba(255, 255, 255, 0.08);
    color: #e5e7eb;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 0.6rem 1rem;
    border-radius: 8px;
    cursor: pointer;
}

.btn-tour-skip {
    background: none;
    border: none;
    color: #6b7280;
    font-size: 0.85rem;
    margin-right: 0.75rem;
    cursor: pointer;
}
`;
document.head.appendChild(style);

window.onboardingEngine = new OnboardingTour();
document.addEventListener("DOMContentLoaded", () => {
    window.onboardingEngine.init();
});
