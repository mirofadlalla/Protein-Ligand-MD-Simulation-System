# Architecture Diagrams & Visual References

This document contains visual representations of the system architecture using Mermaid diagrams, which can be rendered in GitHub, GitLab, and other markdown viewers.

---

## 1. System Component Flow

```mermaid
graph TB
    Client["🖥️ Client/User"]
    API["🌐 Flask REST API"]
    JobMgr["📋 Job Manager"]
    ThreadPool["⚙️ Thread Pool"]
    Pipeline["🔄 7-Stage Pipeline"]
    Storage["💾 File Storage<br/>(data/)"]
    Analysis["📊 Analysis Engine"]
    Download["⬇️ Download ZIP"]
    
    Client -->|REST Calls| API
    API -->|Submit/Query| JobMgr
    JobMgr -->|Execute| ThreadPool
    ThreadPool -->|Run| Pipeline
    Pipeline -->|Read/Write| Storage
    Pipeline -->|Trigger| Analysis
    API -->|Retrieve| Storage
    API -->|Serve| Download
    
    style Client fill:#e1f5ff
    style API fill:#fff3e0
    style JobMgr fill:#fce4ec
    style ThreadPool fill:#f3e5f5
    style Pipeline fill:#e8f5e9
    style Storage fill:#fbe9e7
    style Analysis fill:#e0f2f1
    style Download fill:#f1f8e9
```

---

## 2. Complete MD Pipeline Stages

```mermaid
graph LR
    Input["📁 Input:<br/>protein.pdb<br/>ligand.pdb"]
    
    S1["<b>Stage 1</b><br/>Protein Prep<br/>PDBFixer"]
    S2["<b>Stage 2</b><br/>Ligand Prep<br/>OpenBabel"]
    S3["<b>Stage 3</b><br/>GAFF2 Params<br/>antechamber"]
    S4["<b>Stage 4</b><br/>Topology<br/>tleap"]
    S5["<b>Stage 5</b><br/>Minimization<br/>OpenMM"]
    S6["<b>Stage 6</b><br/>Equilibration<br/>OpenMM"]
    S7["<b>Stage 7</b><br/>Production<br/>OpenMM"]
    S8["<b>Stage 8</b><br/>Package<br/>ZIP"]
    
    Output["📦 Output:<br/>Trajectories<br/>Energies<br/>Structures"]
    
    Input --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> S5
    S5 --> S6
    S6 --> S7
    S7 --> S8
    S8 --> Output
    
    style Input fill:#c8e6c9,stroke:#388e3c,stroke-width:3px
    style S1 fill:#bbdefb,stroke:#1976d2
    style S2 fill:#bbdefb,stroke:#1976d2
    style S3 fill:#ffe0b2,stroke:#f57c00
    style S4 fill:#ffe0b2,stroke:#f57c00
    style S5 fill:#f8bbd0,stroke:#c2185b
    style S6 fill:#f8bbd0,stroke:#c2185b
    style S7 fill:#f8bbd0,stroke:#c2185b
    style S8 fill:#d1c4e9,stroke:#512da8
    style Output fill:#c8e6c9,stroke:#388e3c,stroke-width:3px
```

---

## 3. Request/Response Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant JobMgr as Job Manager
    participant Executor as ThreadPool
    participant Pipeline as MD Pipeline
    participant Storage as File Storage
    
    Client->>API: POST /process<br/>(protein.pdb, ligand.pdb)
    activate API
    API->>API: Validate uploads
    API->>JobMgr: Submit job
    deactivate API
    
    activate JobMgr
    JobMgr->>Storage: Create job dir
    JobMgr->>Executor: Queue task
    JobMgr-->>API: Return job_id
    deactivate JobMgr
    
    API-->>Client: 202 Accepted + job_id
    
    Note over Client,Pipeline: Parallel: Client polls & Pipeline executes
    
    Client->>API: GET /status/job_id
    activate API
    API->>JobMgr: Get status
    activate JobMgr
    JobMgr-->>API: Return status
    deactivate JobMgr
    API-->>Client: JSON status
    deactivate API
    
    par Pipeline Execution
        activate Executor
        Executor->>Pipeline: run_full_pipeline()
        activate Pipeline
        
        Pipeline->>Storage: Stage 1: Prepare protein
        Pipeline->>Storage: Stage 2: Prepare ligand
        Pipeline->>Storage: Stage 3: GAFF2 params
        Pipeline->>Storage: Stage 4: Build topology
        Pipeline->>Storage: Stage 5: Minimization
        Pipeline->>Storage: Stage 6: Equilibration
        Pipeline->>Storage: Stage 7: Production MD
        Pipeline->>Storage: Stage 8: Package results
        
        Pipeline->>JobMgr: Update status
        Pipeline-->>Storage: Write final outputs
        deactivate Pipeline
        deactivate Executor
    end
    
    Client->>API: GET /status/job_id
    activate API
    API->>JobMgr: Get status
    JobMgr-->>API: "completed"
    API-->>Client: Status: completed
    deactivate API
    
    Client->>API: GET /download/job_id
    activate API
    API->>Storage: Read results.zip
    API-->>Client: Binary ZIP
    deactivate API
    
    Client->>API: POST /analyze<br/>(job_id, analyses)
    activate API
    API->>JobMgr: Submit analysis job
    activate JobMgr
    JobMgr->>Executor: Queue analysis task
    JobMgr-->>API: Return analysis_job_id
    deactivate JobMgr
    API-->>Client: 202 Accepted
    deactivate API
```

---

## 4. Data Directory Structure (Runtime)

```mermaid
graph TD
    ROOT["data/"]
    
    JOB1["job_abc123/"]
    JOB2["job_def456/"]
    
    IN1["inputs/"]
    WORK1["work/"]
    RES1["results/"]
    AN1["analysis/"]
    LOGS1["logs/"]
    
    INF["protein_raw.pdb<br/>ligand_raw.pdb"]
    
    WF["protein_fixed.pdb<br/>ligand_clean.mol2<br/>ligand.gaff2.mol2<br/>GAFF_LIGcheck.frcmod<br/>solvated.inpcrd<br/>solvated.prmtop<br/>...other working files"]
    
    RF["production.dcd<br/>production.nc<br/>energies.csv<br/>final.pdb<br/>manifest.json"]
    
    AF["rmsd.csv<br/>rmsd_plot.png<br/>rmsf.csv<br/>rmsf_plot.png<br/>pca_coords.csv<br/>pca_plot.png<br/>prolif_frame_0.pkl<br/>lie_results.csv"]
    
    LF["job_abc123.log"]
    
    ROOT --> JOB1
    ROOT --> JOB2
    ROOT --> "|... more jobs|"
    
    JOB1 --> IN1
    JOB1 --> WORK1
    JOB1 --> RES1
    JOB1 --> AN1
    JOB1 --> LOGS1
    
    IN1 --> INF
    WORK1 --> WF
    RES1 --> RF
    AN1 --> AF
    LOGS1 --> LF
    
    style ROOT fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style JOB1 fill:#e1f5fe,stroke:#01579b
    style IN1 fill:#c8e6c9,stroke:#2e7d32
    style WORK1 fill:#ffe0b2,stroke:#e65100
    style RES1 fill:#f8bbd0,stroke:#880e4f
    style AN1 fill:#e0f2f1,stroke:#00695c
    style LOGS1 fill:#fce4ec,stroke:#c2185b
```

---

## 5. Module Dependencies

```mermaid
graph TD
    RUN["run.py<br/>CLI Entry"]
    
    MAIN["main.py<br/>App Factory"]
    ROUTES["routes.py<br/>Endpoints"]
    SCHEMAS["schemas.py<br/>Data Models"]
    CONFIG["config.py<br/>Config"]
    
    ORCH["orchestrator.py<br/>Pipeline Coordinator"]
    PREP["prepare.py<br/>Stage 1-2"]
    TOPO["topology.py<br/>Stage 3-4"]
    SIM["simulate.py<br/>Stage 5-7"]
    ANALYZE["analyze.py<br/>Post-Analysis"]
    
    JOB_MGR["job_manager.py<br/>Job Registry"]
    FILE_UTILS["file_utils.py<br/>File I/O"]
    
    RUN --> MAIN
    RUN --> CONFIG
    
    MAIN --> ROUTES
    MAIN --> CONFIG
    
    ROUTES --> SCHEMAS
    ROUTES --> ORCH
    ROUTES --> JOB_MGR
    ROUTES --> FILE_UTILS
    
    JOB_MGR --> ORCH
    JOB_MGR --> CONFIG
    
    ORCH --> PREP
    ORCH --> TOPO
    ORCH --> SIM
    ORCH --> ANALYZE
    ORCH --> FILE_UTILS
    
    PREP --> CONFIG
    TOPO --> CONFIG
    SIM --> CONFIG
    ANALYZE --> CONFIG
    
    FILE_UTILS --> CONFIG
    
    style RUN fill:#ffccbc,stroke:#bf360c
    style MAIN fill:#c8e6c9,stroke:#2e7d32
    style ROUTES fill:#bbdefb,stroke:#1565c0
    style SCHEMAS fill:#ece7f7,stroke:#5e35b1
    style CONFIG fill:#fff9c4,stroke:#f57f17
    
    style ORCH fill:#ffccbc,stroke:#d84315
    style PREP fill:#c5cae9,stroke:#283593
    style TOPO fill:#c5cae9,stroke:#283593
    style SIM fill:#c5cae9,stroke:#283593
    style ANALYZE fill:#c5cae9,stroke:#283593
    
    style JOB_MGR fill:#f8bbd0,stroke:#ad1457
    style FILE_UTILS fill:#b2dfdb,stroke:#00695c
```

---

## 6. API Endpoint Map

```mermaid
graph TB
    API["Flask REST API<br/>:5005"]
    
    HEALTH["🟢 GET /health<br/>Returns: status"]
    ROOT["🟢 GET /<br/>Returns: status"]
    
    PROCESS["🔵 POST /process<br/>Input: protein, ligand,<br/>parameters<br/>Returns: job_id"]
    
    STATUS["🟢 GET /status/job_id<br/>Returns: job status,<br/>progress, error"]
    
    DOWNLOAD["🟢 GET /download/job_id<br/>Returns: results.zip"]
    
    ANALYZE["🔵 POST /analyze<br/>Input: job_id,<br/>analyses list<br/>Returns: analysis_job_id"]
    
    DLMANYSIS["🟢 GET /download_analysis/job_id<br/>Returns: analysis.zip"]
    
    API --> HEALTH
    API --> ROOT
    API --> PROCESS
    API --> STATUS
    API --> DOWNLOAD
    API --> ANALYZE
    API --> DLMANYSIS
    
    style API fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style HEALTH fill:#c8e6c9,stroke:#2e7d32
    style ROOT fill:#c8e6c9,stroke:#2e7d32
    style PROCESS fill:#bbdefb,stroke:#1565c0
    style STATUS fill:#c8e6c9,stroke:#2e7d32
    style DOWNLOAD fill:#c8e6c9,stroke:#2e7d32
    style ANALYZE fill:#bbdefb,stroke:#1565c0
    style DLMANYSIS fill:#c8e6c9,stroke:#2e7d32
```

---

## 7. Job State Machine

```mermaid
stateDiagram-v2
    [*] --> Submitted: POST /process
    
    Submitted --> Queued: Job queued
    
    Queued --> Running: ThreadPool available
    
    Running --> Running: Update status<br/>Step X/8
    
    Running --> Completed: All stages pass
    Running --> Failed: Stage error
    
    Completed --> ReadyDownload: Results packaged
    ReadyDownload --> [*]: Client downloads
    
    Failed --> ReadyDownload: Error logged
    ReadyDownload --> [*]: User sees error
    
    Completed --> AnalysisQueued: POST /analyze
    AnalysisQueued --> AnalysisRunning: Analysis starts
    AnalysisRunning --> AnalysisCompleted: Analysis done
    AnalysisCompleted --> ReadyDownload: Analysis packaged
    
    text1: Submitted → Queued → Running → Completed → Download
    text2: Running → Failed → Error logged
    text3: Completed → Analysis → Download
    
    note right of Running
        7-stage pipeline
        Status updates
        at each stage
    end note
    
    note right of Failed
        Error message
        recorded in
        job status
    end note
    
    note right of ReadyDownload
        Results packaged as ZIP
        Ready for download
    end note
```

---

## 8. Technology Stack Pyramid

```mermaid
graph TB
    subgraph GPU["GPU Acceleration"]
        CUDA["NVIDIA CUDA<br/>OpenCL"]
    end
    
    subgraph MDENGINE["MD Simulation Engine"]
        OPENMM["OpenMM 8.1"]
        AMBER["AmberTools 24"]
    end
    
    subgraph CHEMISTRY["Chemistry & Analysis"]
        GAFF["GAFF2 Force Field"]
        TOOLS["antechamber, tleap,<br/>pdb4amber, pdbfixer"]
        RDKit["RDKit, ProLIF,<br/>MDAnalysis, BioPandas"]
    end
    
    subgraph APPSERVER["Application Server"]
        FLASK["Flask 3.0+, Flask-CORS"]
        JM["Job Manager,<br/>ThreadPool"]
    end
    
    subgraph CONTAINER["Containerization & Deployment"]
        DOCKER["Docker, Docker Compose"]
    end
    
    GPU --> MDENGINE
    MDENGINE --> CHEMISTRY
    CHEMISTRY --> APPSERVER
    APPSERVER --> CONTAINER
    
    style GPU fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    style MDENGINE fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style CHEMISTRY fill:#f8bbd0,stroke:#880e4f,stroke-width:2px
    style APPSERVER fill:#ffe0b2,stroke:#e65100,stroke-width:2px
    style CONTAINER fill:#d1c4e9,stroke:#512da8,stroke-width:2px
```

---

## 9. Solvation & Ion Setup

```mermaid
graph TB
    COMPLEX["Protein-Ligand<br/>Complex"]
    
    BOX["Solvation Box<br/>12 Å padding"]
    WATER["Water Molecules<br/>TIP3P/OPC"]
    NaCl["Counter-ions<br/>NaCl (0.15 M)"]
    
    SOLVATED["Solvated System<br/>Ready for MD"]
    
    COMPLEX -->|tleap| BOX
    BOX -->|Add water| WATER
    WATER -->|Neutralize + Ionic strength| NaCl
    NaCl --> SOLVATED
    
    style COMPLEX fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    style BOX fill:#bbdefb,stroke:#1565c0
    style WATER fill:#b3e5fc,stroke:#0277bd
    style NaCl fill:#fff9c4,stroke:#f57f17
    style SOLVATED fill:#f8bbd0,stroke:#c2185b,stroke-width:2px
```

---

## 10. Equilibration Protocol

```mermaid
graph LR
    MINIM["Energy<br/>Minimization<br/>20k steps<br/>~2 ps"]
    
    EQ["NPT Equilibration<br/>5 ns @ 298 K<br/>Restraints on<br/>protein backbone"]
    
    PROD["Production MD<br/>0.1-∞ ns<br/>Restraints OFF<br/>Unrestrained exploration"]
    
    MINIM -->|"Initialize velocities"| EQ
    EQ -->|"Release restraints"| PROD
    
    style MINIM fill:#f3e5f5,stroke:#5e35b1,stroke-width:2px
    style EQ fill:#fff3e0,stroke:#e65100,stroke-width:2px
    style PROD fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
```

---

## 11. Analysis Module Outputs

```mermaid
graph TD
    TRAJ["MD Trajectory<br/>(DCD/NetCDF)"]
    
    RMSD["RMSD Analysis<br/>Cα, Ligand,<br/>Heavy atoms"]
    
    RMSF["RMSF Analysis<br/>Per-residue<br/>flexibility"]
    
    PCA["Principal Component<br/>Analysis<br/>Motion modes"]
    
    PROLIF["ProLIF<br/>Protein-Ligand<br/>Interactions"]
    
    LIE["LIE Binding<br/>Energy<br/>Estimate"]
    
    PLOTS["Plots<br/>(PNG)"]
    CSV["CSV Data"]
    
    TRAJ --> RMSD
    TRAJ --> RMSF
    TRAJ --> PCA
    TRAJ --> PROLIF
    TRAJ --> LIE
    
    RMSD --> PLOTS
    RMSF --> PLOTS
    PCA --> PLOTS
    
    RMSD --> CSV
    RMSF --> CSV
    PCA --> CSV
    PROLIF --> CSV
    LIE --> CSV
    
    style TRAJ fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    
    style RMSD fill:#bbdefb,stroke:#1565c0
    style RMSF fill:#bbdefb,stroke:#1565c0
    style PCA fill:#bbdefb,stroke:#1565c0
    style PROLIF fill:#ffe0b2,stroke:#e65100
    style LIE fill:#f8bbd0,stroke:#c2185b
    
    style PLOTS fill:#d1c4e9,stroke:#512da8
    style CSV fill:#b2dfdb,stroke:#00695c
```

---

## 12. Error Handling Flow

```mermaid
graph TD
    TRY["Try Stage X"]
    
    SUCCESS{Success?}
    
    YES["Continue to<br/>Stage X+1"]
    
    NO["Catch Exception"]
    
    LOG["Log Error"]
    
    STATUS["Set Job Status<br/>= 'failed'"]
    
    RECORD["Record Error<br/>Message"]
    
    CLEANUP["Cleanup Job<br/>Directory"]
    
    RESPOND["Return Error<br/>to Client"]
    
    TRY --> SUCCESS
    
    SUCCESS -->|Yes| YES
    SUCCESS -->|No| NO
    
    NO --> LOG
    LOG --> STATUS
    STATUS --> RECORD
    RECORD --> CLEANUP
    CLEANUP --> RESPOND
    
    style TRY fill:#c8e6c9,stroke:#2e7d32
    style SUCCESS fill:#ffccbc,stroke:#d84315
    style YES fill:#c8e6c9,stroke:#2e7d32
    style NO fill:#ffccbc,stroke:#bf360c
    style LOG fill:#fff9c4,stroke:#f57f17
    style STATUS fill:#f8bbd0,stroke:#c2185b
    style RECORD fill:#f8bbd0,stroke:#c2185b
    style CLEANUP fill:#f8bbd0,stroke:#c2185b
    style RESPOND fill:#ffccbc,stroke:#bf360c
```

---

## Usage Diagram: Typical User Workflow

```mermaid
graph TB
    USER["👤 User/<br/>Researcher"]
    
    PREP["🧬 Prepare<br/>PDB Files<br/>protein.pdb<br/>ligand.pdb"]
    
    UPLOAD["📤 Upload via API<br/>or Web Interface"]
    
    SUBMIT["🚀 Submit<br/>POST /process"]
    
    MONITOR["📊 Monitor Progress<br/>GET /status"]
    
    WAIT["⏳ Wait for Completion<br/>5-30 minutes"]
    
    DOWNLOAD["⬇️ Download Results<br/>GET /download"]
    
    ANALYZE["🔬 Optional Analysis<br/>POST /analyze"]
    
    VIZ["📈 Visualize<br/>RMSD, RMSF, PCA<br/>Plots"]
    
    REPORT["📝 Write Report<br/>Publish Results"]
    
    USER --> PREP
    PREP --> UPLOAD
    UPLOAD --> SUBMIT
    SUBMIT --> MONITOR
    MONITOR --> WAIT
    WAIT --> DOWNLOAD
    DOWNLOAD --> ANALYZE
    ANALYZE --> VIZ
    VIZ --> REPORT
    
    style USER fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    style PREP fill:#c8e6c9,stroke:#2e7d32
    style UPLOAD fill:#ffccbc,stroke:#d84315
    style SUBMIT fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    style MONITOR fill:#b3e5fc,stroke:#0277bd
    style WAIT fill:#d1c4e9,stroke:#512da8
    style DOWNLOAD fill:#fff9c4,stroke:#f57f17
    style ANALYZE fill:#f8bbd0,stroke:#c2185b,stroke-width:2px
    style VIZ fill:#d1c4e9,stroke:#512da8
    style REPORT fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
```

---

## Performance Comparison: CPU vs GPU

### Execution Time Profile

For a typical 0.1 ns production MD run:

```
CPU (4 cores):        ████████████████████████ 60 min
CPU (8 cores):        ████████████████ 40 min
GPU (RTX 3080):       ██ 2 min
GPU (A100):           █ 1 min
```

### Memory Profile

```
CPU simulation:       ██████ 8 GB
GPU simulation:       ████████████ 12 GB (GPU memory)
```

---

## Troubleshooting Decision Tree

```
ERROR FROM GET /status/<job_id>
│
├─ Status = "running"?
│  └─ EXPECTED: Wait and poll again
│
├─ Status = "completed"?
│  └─ Good! Make GET /download/<job_id>
│
├─ Status = "failed"?
│  └─ Check error message
│    ├─ "PDB parsing error"?
│    │  └─ FIX: Validate PDB format
│    ├─ "antechamber failed"?
│    │  └─ FIX: Check ligand structure
│    ├─ "tleap failed"?
│    │  └─ FIX: Verify GAFF2 parameters
│    ├─ "Simulation diverged"?
│    │  └─ FIX: Reduce timestep, increase minimization
│    └─ "Out of memory"?
│       └─ FIX: Reduce simulation time, use GPU
│
└─ Job not found (404)?
   └─ FIX: Check job_id spelling, retry POST /process
```

---

## End of Visual Documentation

For detailed explanations of each component, architecture decisions, and API usage, refer to [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md).
