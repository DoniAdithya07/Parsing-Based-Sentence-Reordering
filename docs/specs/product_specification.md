# Product Specification Document: 3D Immersive AI Parsing-Based Sentence Reordering

## 1. Product Overview
The **AI Parsing-Based Sentence Reordering** application is evolving from a traditional DOM-based web UI into a **fully immersive, cinematic 3D WebGL experience**. This transition aims to improve user engagement by transforming the process of sentence analysis and NLP interactions into a spatial format. Users will step into a minimalistic, monochrome 3D "void" where they can input text, trigger parsing sequences, and visualize dependency paths in an interactive tridimensional space.

## 2. Target Audience
*   **Data Scientists & Linguists:** Seeking deeper visualizations of grammatical structures (Subject, Verb, Object) than traditional tables can provide.
*   **Tech Enthusiasts & Developers:** Interested in state-of-the-art interactive web experiences bridging AI/NLP and Three.js.
*   **Educational Institutions:** Needing visual ways to teach syntax routing, NLP pipelines, and dependency parsing.

---

## 3. Tech Stack Requirements

### Frontend (The 3D Interface)
*   **Core Framework**: React 18+ (Next.js or Vite).
*   **3D Graphics & Rendering**: Three.js, React Three Fiber (R3F), and `@react-three/drei` for robust WebGL bindings.
*   **Animation & Orchestration**: Framer Motion / Framer Motion 3D for smooth element transitions, and GSAP for advanced scroll-linked timeline sequences.
*   **Overlay & UI**: Tailwind CSS for building minimal, flat HTML overlays (like Login/Authentication elements).

### Backend (Existing Infrastructure)
*   **API Framework**: Python, Flask (providing REST endpoints).
*   **NLP Engine**: spaCy and NLTK for core dependency parsing and reordering logic.
*   **Authentication**: Firebase Auth (Google Sign-In).

---

## 4. Design & UX Guidelines

### 4.1 Aesthetic
*   **Monochrome & Minimalist**: A stark contrast between black, white, and deep grays. Use post-processing (Bloom, slight chromatic aberration, noise) to make the void feel vast and atmospheric.
*   **Lighting**: Dramatic directional lighting and soft ambient layers to give floating panels a physical presence.

### 4.2 Spatial Navigation
*   **Scroll-Linked Camera**: Moving the scroll wheel lerps the camera deeper into the Z-axis, passing contextual 3D typographic elements and interactive "stations".
*   **Interactive 3D Elements**: The interface uses "physical" panels. Buttons physically depress and react to hover states (raycasting). Text input is mapped onto 3D planes using `<Html>` overlays or Text geometry.

---

## 5. Functional Requirements

### 5.1 The "Void" Journey (User Flow)
1.  **Landing / Home Station:** The camera starts at a floating 3D title text. A physical "Start Parsing" button pulls the camera forward.
2.  **Input Station:** A transparent glass-morphic floating panel accepts text input. Users can either type their own sentences or press a nearby 3D toggle to load examples from the Reuters dataset via `GET /api/sample`.
3.  **Processing Tunnel:** Upon form submission (`POST /api/reorder`), the camera fast-forwards through a transient particle tunnel representing data processing.
4.  **Results Station:** 
    *   **Baseline Output vs. Parsing Output:** Displayed as two contrasting floating monoliths.
    *   **Node Graph Visualization:** 3D glowing lines linking subject, verb, and object parts of the sentences, visualizing the dependency structure returned by the existing spaCy algorithm.

### 5.2 Backend API Integration
The 3D application acts as a client to the existing Flask APIs. The interface must successfully parse and visualize outputs from:
*   `POST /api/reorder`: Handle the returned `baseline`, `parser`, or `compare` payload data to construct the Results Station.
*   `GET /api/sample`: Fetch Reuters-21578 samples to populate input fields.
*   **History & Auth**: Use `POST /api/history` and Firebase flows to save valid runs without interrupting the 3D camera focus.

---

## 6. Non-Functional Requirements

### 6.1 Performance and Rendering
*   **60 Frames Per Second (FPS)**: WebGL scenes must be heavily optimized (instanced mesh geometry, recycled materials, compressed textures, `drei/PerformanceMonitor`) to guarantee smooth scroll experiences on mid-tier dedicated hardware.
*   **Graceful Degradation**: Devices with low capabilities should disable post-processing and drop pixel ratios instead of lagging.

### 6.2 Responsive Behavior
*   The camera's Field of View (FOV) and UI panel placement must adapt dynamically to screen aspect ratios. On mobile, elements stack closely on the Z-axis; on desktop, they take advantage of horizontal layout.
*   Touch support must be implemented for orbit controls (if utilized) and screen swiping as an equivalent to scroll-linked movement.

---

## 7. Development Phases

1.  **Phase 1: 3D Environment Scaffolding**
    *   Initialize React Next.js/Vite project.
    *   Set up R3F canvas, scroll controls, and camera paths.
2.  **Phase 2: Backend Wiring & State Management**
    *   Connect Flask `/api/reorder` to the frontend state.
    *   Map JSON responses to spatial positions.
3.  **Phase 3: Interactive Physics & Data Visualization**
    *   Build 3D DOM overlays for input.
    *   Render dependency trees as spatial particle graphs.
4.  **Phase 4: Optimization, Polish, and Lighting**
    *   Passes for Framer Motion transitions, materials, bloom effects, and responsive resizing.
