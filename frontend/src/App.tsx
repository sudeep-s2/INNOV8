import React, { useState, useEffect } from 'react';
import { checkHealth, analyzeSource, uploadSourceFile, transformOutputs } from './services/api';
import type {
  HealthResponse,
  StructuredContentModel,
  TransformationConfig,
  OutputType,
  MultiTransformResponse,
  Audience,
  Tone,
  DetailLevel,
  Objective,
  SourceChunk
} from './types';
import './App.css';

const SAMPLE_TEXT = `NATIONAL CRITICAL INFRASTRUCTURE DEFENCE
Classification: Restricted | Ref: NTRO-CYBER-2026-08

SECTION 1: INCIDENT OVERVIEW
Sensors detected unauthorized reconnaissance activity targeting 4 regional load dispatch centers.
The threat group, tracked as APT-44, exploited an unpatched zero-day vulnerability in industrial SCADA gateways (CVE-2026-38910, CVSS 9.8).
Approximately 4.8 Gigabytes of routing configuration files were exfiltrated on 2026-08-10.

SECTION 2: REMEDIATION DIRECTIVES
Grid security authorities recommend isolating all SCADA IEC-104 ports (TCP 2404) immediately.
Operators must deploy emergency firmware hotfix KB-2026-08 across all gateway controllers within 24 hours.`;

type WorkflowStage = 1 | 2 | 3 | 4 | 5;

export const App: React.FC = () => {
  // Navigation & Workflow Stage
  const [currentStage, setCurrentStage] = useState<WorkflowStage>(1);

  // Backend Connection State
  const [healthStatus, setHealthStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);

  // Stage 1: Ingestion State
  const [inputMode, setInputMode] = useState<'upload' | 'paste'>('paste');
  const [sourceText, setSourceText] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [analysisError, setAnalysisError] = useState<string>('');

  // Stage 2: Canonical Structured Model State
  const [structuredModel, setStructuredModel] = useState<StructuredContentModel | null>(null);
  const [activeInspectedChunk, setActiveInspectedChunk] = useState<SourceChunk | null>(null);

  // Stage 3: Transformation Configuration State
  const [config, setConfig] = useState<TransformationConfig>({
    audience: 'executive',
    tone: 'professional',
    detail_level: 'standard',
    objective: 'inform',
    language: 'English'
  });

  const [selectedOutputs, setSelectedOutputs] = useState<OutputType[]>([
    'executive_summary',
    'advisory_brief',
    'public_communication',
    'presentation'
  ]);

  // Stage 4 & 5: Generation & Results State
  const [isTransforming, setIsTransforming] = useState<boolean>(false);
  const [transformResults, setTransformResults] = useState<MultiTransformResponse | null>(null);
  const [activeOutputTab, setActiveOutputTab] = useState<OutputType>('executive_summary');
  const [transformError, setTransformError] = useState<string>('');
  const [generationProgress, setGenerationProgress] = useState<string>('Initializing orchestration...');

  // Health check on initial load
  useEffect(() => {
    checkHealth()
      .then((data) => {
        setHealthData(data);
        setHealthStatus('connected');
      })
      .catch(() => {
        setHealthStatus('disconnected');
      });
  }, []);

  // Quick Sample Loader
  const handleLoadSample = () => {
    setInputMode('paste');
    setSourceText(SAMPLE_TEXT);
    setAnalysisError('');
  };

  // Stage 1 -> Stage 2: Canonical Analysis
  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setAnalysisError('');
    setStructuredModel(null);
    setTransformResults(null);
    setCurrentStage(1);

    try {
      let model: StructuredContentModel;
      if (inputMode === 'upload' && selectedFile) {
        const ingestRes = await uploadSourceFile(selectedFile);
        model = await analyzeSource({ chunks: ingestRes.chunks });
      } else {
        if (!sourceText.trim() || sourceText.trim().length < 10) {
          throw new Error('Please provide at least 10 characters of source material.');
        }
        model = await analyzeSource({ source_text: sourceText.trim() });
      }
      setStructuredModel(model);
      if (model.source_chunks && model.source_chunks.length > 0) {
        setActiveInspectedChunk(model.source_chunks[0]);
      }
      setCurrentStage(2);
    } catch (err: any) {
      setAnalysisError(err.message || 'Canonical analysis failed. Please verify Ollama is running.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Output selection toggling
  const toggleOutputType = (type: OutputType) => {
    setSelectedOutputs((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  // Stage 3 -> Stage 4 -> Stage 5: Multi-Output Generation
  const handleTransform = async () => {
    if (!structuredModel) return;
    if (selectedOutputs.length === 0) {
      setTransformError('Please select at least one output format to generate.');
      return;
    }

    setIsTransforming(true);
    setCurrentStage(4);
    setTransformError('');
    setGenerationProgress('Orchestrating multi-output transformation via local Qwen3 8B...');

    try {
      const response = await transformOutputs({
        structured_model: structuredModel,
        config: config,
        output_types: selectedOutputs
      });
      setTransformResults(response);
      if (selectedOutputs.length > 0 && !selectedOutputs.includes(activeOutputTab)) {
        setActiveOutputTab(selectedOutputs[0]);
      }
      setCurrentStage(5);
    } catch (err: any) {
      setTransformError(err.message || 'Transformation orchestration failed.');
      setCurrentStage(3);
    } finally {
      setIsTransforming(false);
    }
  };

  const selectChunkById = (chunkId: string) => {
    if (!structuredModel) return;
    const found = structuredModel.source_chunks.find((c) => c.chunk_id === chunkId);
    if (found) {
      setActiveInspectedChunk(found);
    }
  };

  const handleResetAll = () => {
    setStructuredModel(null);
    setTransformResults(null);
    setSourceText('');
    setSelectedFile(null);
    setActiveInspectedChunk(null);
    setCurrentStage(1);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#0c1421] text-[#dbe2f5]">
      {/* Top Glass Institutional Header */}
      <header className="glass-header sticky top-0 z-50 w-full px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4">
          {/* Brand Logo & Meta */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-blue-700 to-indigo-500 flex items-center justify-center shadow-md">
              <span className="material-symbols-outlined text-white text-[22px]">hub</span>
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <span className="font-bold text-lg text-white tracking-tight">Info2Impact</span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30 uppercase">
                  SIH26154 · NTRO
                </span>
              </div>
              <span className="text-xs text-[#8d98b0] -mt-0.5">Automated Content Transformation Platform</span>
            </div>
          </div>

          {/* Stepper Navigation */}
          <nav className="hidden md:flex items-center stepper-nav">
            <button
              type="button"
              className={`step-item ${currentStage === 1 ? 'active' : ''} ${structuredModel ? 'completed' : ''}`}
              onClick={() => setCurrentStage(1)}
            >
              <span className="step-badge">
                {structuredModel ? <span className="material-symbols-outlined text-[13px]">check</span> : '1'}
              </span>
              <span>Source</span>
            </button>
            <span className="text-[#434e62] text-xs">/</span>

            <button
              type="button"
              className={`step-item ${currentStage === 2 ? 'active' : ''} ${structuredModel ? 'completed' : ''}`}
              onClick={() => structuredModel && setCurrentStage(2)}
              disabled={!structuredModel}
            >
              <span className="step-badge">
                {structuredModel ? <span className="material-symbols-outlined text-[13px]">check</span> : '2'}
              </span>
              <span>Understand</span>
            </button>
            <span className="text-[#434e62] text-xs">/</span>

            <button
              type="button"
              className={`step-item ${currentStage === 3 ? 'active' : ''} ${transformResults ? 'completed' : ''}`}
              onClick={() => structuredModel && setCurrentStage(3)}
              disabled={!structuredModel}
            >
              <span className="step-badge">
                {transformResults ? <span className="material-symbols-outlined text-[13px]">check</span> : '3'}
              </span>
              <span>Configure</span>
            </button>
            <span className="text-[#434e62] text-xs">/</span>

            <button
              type="button"
              className={`step-item ${currentStage === 4 ? 'active' : ''}`}
              disabled={!isTransforming}
            >
              <span className="step-badge">4</span>
              <span>Generate</span>
            </button>
            <span className="text-[#434e62] text-xs">/</span>

            <button
              type="button"
              className={`step-item ${currentStage === 5 ? 'active' : ''} ${transformResults ? 'completed' : ''}`}
              onClick={() => transformResults && setCurrentStage(5)}
              disabled={!transformResults}
            >
              <span className="step-badge">5</span>
              <span>Review</span>
            </button>
          </nav>

          {/* Right Status Badge */}
          <div className="flex items-center gap-3 shrink-0">
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                healthStatus === 'connected'
                  ? 'bg-emerald-950/40 text-emerald-400 border-emerald-700/40'
                  : healthStatus === 'disconnected'
                  ? 'bg-red-950/40 text-red-400 border-red-700/40'
                  : 'bg-amber-950/40 text-amber-400 border-amber-700/40'
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  healthStatus === 'connected' ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
                }`}
              ></span>
              {healthStatus === 'connected' ? `Ollama Qwen3:8B (${healthData?.service || 'online'})` : 'Backend Offline'}
            </span>

            {structuredModel && (
              <button
                type="button"
                onClick={handleResetAll}
                className="text-xs px-2.5 py-1 rounded bg-[#222a38] hover:bg-[#2d3543] text-[#8d98b0] hover:text-white transition-colors"
                title="Start a new document transformation"
              >
                Reset
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-8 flex flex-col gap-8">
        
        {/* ======================================================== */}
        {/* STAGE 1: SOURCE INGESTION */}
        {/* ======================================================== */}
        {currentStage === 1 && (
          <div className="max-w-4xl w-full mx-auto flex flex-col gap-6">
            <div className="flex flex-col items-center text-center gap-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#18202d] text-blue-400 font-mono text-xs uppercase tracking-wider border border-[#26364a]">
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"></span>
                Stage 1 of 5 · Ingestion Layer
              </div>
              <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight mt-1">
                Add Source Document
              </h1>
              <p className="text-[#8d98b0] text-sm sm:text-base max-w-xl">
                Ingest technical intelligence dossiers, regulatory mandates, or incident telemetry to extract a canonical factual baseline.
              </p>
            </div>

            <div className="command-card p-6 sm:p-8 flex flex-col gap-6">
              <div className="glow-orb-primary -top-24 -right-24"></div>
              <div className="glow-orb-secondary -bottom-24 -left-24"></div>

              {/* Mode Toggle Header */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-[#26364a] pb-4">
                <div className="inline-flex p-1 rounded-lg bg-[#141c29] border border-[#26364a]">
                  <button
                    type="button"
                    className={`toggle-tab ${inputMode === 'paste' ? 'active' : ''}`}
                    onClick={() => setInputMode('paste')}
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[17px]">edit_note</span>
                      Paste Raw Text
                    </span>
                  </button>
                  <button
                    type="button"
                    className={`toggle-tab ${inputMode === 'upload' ? 'active' : ''}`}
                    onClick={() => setInputMode('upload')}
                  >
                    <span className="flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[17px]">upload_file</span>
                      Upload Document (.txt / .pdf)
                    </span>
                  </button>
                </div>

                <button
                  type="button"
                  onClick={handleLoadSample}
                  className="text-xs text-blue-400 hover:text-blue-300 transition-colors flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-[16px]">download_for_offline</span>
                  Load Sample NTRO SCADA Incident
                </button>
              </div>

              {/* Input Body */}
              {inputMode === 'paste' ? (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between text-xs text-[#8d98b0] font-mono">
                    <span className="uppercase tracking-wider">Source Content Buffer</span>
                    <span>{sourceText.length} characters · ~{sourceText.split(/\s+/).filter(Boolean).length} words</span>
                  </div>
                  <textarea
                    rows={9}
                    className="w-full bg-[#141c29] text-[#dbe2f5] p-4 rounded-lg border border-[#26364a] focus:border-blue-500 focus:outline-none font-mono text-sm leading-relaxed transition-colors shadow-inner"
                    placeholder="Paste briefing report, cyber incident dossier, or policy document excerpt here..."
                    value={sourceText}
                    onChange={(e) => setSourceText(e.target.value)}
                  />
                  <span className="text-xs text-[#64748b] flex items-center gap-1 mt-1">
                    <span className="material-symbols-outlined text-[15px] text-blue-400">info</span>
                    Markdown headers, technical identifiers (CVEs, IPs), and numbered clauses will be preserved with exact offsets.
                  </span>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="relative rounded-xl border-2 border-dashed border-[#26364a] hover:border-blue-500/60 bg-[#141c29] p-8 flex flex-col items-center justify-center text-center transition-all cursor-pointer">
                    <input
                      type="file"
                      accept=".txt,.pdf"
                      className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                      onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    />
                    <div className="w-14 h-14 rounded-xl bg-[#18202d] border border-[#26364a] flex items-center justify-center text-blue-400 mb-3 shadow-md">
                      <span className="material-symbols-outlined text-[30px]">cloud_upload</span>
                    </div>
                    <span className="text-white font-medium text-base">
                      {selectedFile ? selectedFile.name : 'Drag & drop document here, or click to browse'}
                    </span>
                    <span className="text-xs text-[#8d98b0] mt-1">
                      Supported formats: Structured PDF, Plain TXT · Air-gapped local processing
                    </span>
                  </div>

                  {selectedFile && (
                    <div className="command-card-high p-4 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="material-symbols-outlined text-red-400 text-[26px]">picture_as_pdf</span>
                        <div className="flex flex-col">
                          <span className="text-sm font-medium text-white">{selectedFile.name}</span>
                          <span className="text-xs text-[#8d98b0]">{(selectedFile.size / 1024).toFixed(1)} KB · Ready for token chunking</span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setSelectedFile(null)}
                        className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded bg-[#18202d]"
                      >
                        Remove
                      </button>
                    </div>
                  )}
                </div>
              )}

              {analysisError && (
                <div className="p-4 rounded-lg bg-red-950/40 border border-red-700/50 text-red-300 text-sm flex items-start gap-2">
                  <span className="material-symbols-outlined text-[18px] text-red-400 shrink-0 mt-0.5">error</span>
                  <div>
                    <strong>Analysis Failed:</strong> {analysisError}
                  </div>
                </div>
              )}

              {/* Action Trigger */}
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
                <div className="flex items-center gap-2 text-xs text-[#8d98b0]">
                  <span className="material-symbols-outlined text-[16px] text-emerald-400">verified_user</span>
                  <span>Zero-Cloud Retention · Local Ollama Qwen3:8B Enclave</span>
                </div>

                <button
                  type="button"
                  className="btn-command btn-primary-command w-full sm:w-auto"
                  onClick={handleAnalyze}
                  disabled={isAnalyzing || (inputMode === 'paste' && !sourceText.trim()) || (inputMode === 'upload' && !selectedFile)}
                >
                  {isAnalyzing ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                      <span>Deconstructing Factual Model...</span>
                    </>
                  ) : (
                    <>
                      <span>Analyze & Extract Canonical Model</span>
                      <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STAGE 2: UNDERSTAND (CANONICAL MODEL & INSPECTOR) */}
        {/* ======================================================== */}
        {currentStage === 2 && structuredModel && (
          <div className="flex flex-col gap-6">
            {/* Header Status Bar */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-blue-400 font-mono text-xs uppercase tracking-wider mb-1">
                  <span>Stage 2 of 5</span>
                  <span>·</span>
                  <span>Canonical Source of Truth</span>
                </div>
                <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                  Canonical Structured Understanding
                </h2>
                <p className="text-sm text-[#8d98b0]">
                  Source deconstructed into structured facts, metrics, risks, and recommendations with verified chunk provenance.
                </p>
              </div>

              <button
                type="button"
                className="btn-command btn-primary-command self-start sm:self-auto shrink-0"
                onClick={() => setCurrentStage(3)}
              >
                <span>Proceed to Configure</span>
                <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
              </button>
            </div>

            {/* Executive Synthesis Card */}
            <div className="command-card p-6 border-blue-900/60 bg-[#121c2c]">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2 text-blue-400 font-mono text-xs uppercase">
                  <span className="material-symbols-outlined text-[18px]">psychology</span>
                  <span>Primary Subject & Synthesis</span>
                </div>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-900/40 text-emerald-300 border border-emerald-700/40">
                  Grounding Verified · 0 Hallucinations
                </span>
              </div>
              <h3 className="text-xl font-bold text-white mb-2">{structuredModel.topic}</h3>
              <p className="text-sm text-[#c3cce0] leading-relaxed">{structuredModel.summary}</p>

              {/* Quick Metrics Bar */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-[#26364a]">
                <div className="flex flex-col">
                  <span className="text-[11px] font-mono uppercase text-[#8d98b0]">Key Facts</span>
                  <span className="text-lg font-bold text-white">{structuredModel.key_facts.length} Verified</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] font-mono uppercase text-[#8d98b0]">Metrics</span>
                  <span className="text-lg font-bold text-emerald-400">{structuredModel.metrics.length} Extracted</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] font-mono uppercase text-[#8d98b0]">Risks Identified</span>
                  <span className="text-lg font-bold text-amber-400">{structuredModel.risks.length} Prioritized</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-[11px] font-mono uppercase text-[#8d98b0]">Source Chunks</span>
                  <span className="text-lg font-bold text-blue-400">{structuredModel.source_chunks.length} Segmented</span>
                </div>
              </div>
            </div>

            {/* Split Grid: Facts/Risks + Forensic Source Inspector */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left 7 Columns: Extracted Model Components */}
              <div className="lg:col-span-7 flex flex-col gap-5">
                {/* Verified Facts */}
                <div className="command-card p-5">
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-3 flex items-center gap-2">
                    <span className="material-symbols-outlined text-blue-400 text-[18px]">fact_check</span>
                    Extracted Facts with Provenance
                  </h4>
                  <div className="flex flex-col gap-3">
                    {structuredModel.key_facts.map((fact) => (
                      <div
                        key={fact.fact_id}
                        className="p-3 rounded-lg bg-[#141c29] border border-[#26364a] hover:border-blue-500/40 transition-colors"
                      >
                        <div className="flex items-center justify-between gap-2 mb-1.5">
                          <span className="text-xs font-mono text-blue-300 font-bold">{fact.fact_id}</span>
                          <div className="flex items-center gap-1">
                            {fact.source_chunk_ids.map((cid) => (
                              <button
                                key={cid}
                                type="button"
                                onClick={() => selectChunkById(cid)}
                                className={`citation-pill ${activeInspectedChunk?.chunk_id === cid ? 'selected' : ''}`}
                                title="Click to inspect exact source chunk"
                              >
                                {cid}
                              </button>
                            ))}
                          </div>
                        </div>
                        <p className="text-xs text-[#dbe2f5]">{fact.statement}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Risks & Recommendations */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="command-card p-4">
                    <h4 className="text-xs font-bold text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[16px]">warning</span>
                      Risks & Exposure
                    </h4>
                    <ul className="flex flex-col gap-2">
                      {structuredModel.risks.map((r, i) => (
                        <li key={i} className="text-xs text-[#dbe2f5] bg-[#141c29] p-2.5 rounded border border-amber-900/30">
                          <span className="font-semibold text-amber-300 block mb-0.5">{r.severity || 'Critical'} Severity</span>
                          {r.risk}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="command-card p-4">
                    <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <span className="material-symbols-outlined text-[16px]">assignment_turned_in</span>
                      Actionable Directives
                    </h4>
                    <ul className="flex flex-col gap-2">
                      {structuredModel.recommendations.map((rec, i) => (
                        <li key={i} className="text-xs text-[#dbe2f5] bg-[#141c29] p-2.5 rounded border border-emerald-900/30">
                          <span className="font-semibold text-emerald-300 block mb-0.5">{rec.priority || 'Immediate'}</span>
                          {rec.action}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {/* Right 5 Columns: Forensic Source Inspector */}
              <div className="lg:col-span-5 sticky top-20">
                <div className="command-card p-5 bg-[#141c29] border-blue-900/50">
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#26364a]">
                    <div className="flex items-center gap-2 text-blue-400 font-mono text-xs uppercase font-bold">
                      <span className="material-symbols-outlined text-[18px]">find_in_page</span>
                      <span>Forensic Source Inspector</span>
                    </div>
                    {activeInspectedChunk && (
                      <span className="citation-pill-verified font-mono text-xs">
                        {activeInspectedChunk.chunk_id}
                      </span>
                    )}
                  </div>

                  {activeInspectedChunk ? (
                    <div className="flex flex-col gap-3">
                      <div className="flex items-center justify-between text-xs text-[#8d98b0] font-mono">
                        <span>Location: {activeInspectedChunk.source_location || 'Body Passage'}</span>
                        <span>Page {activeInspectedChunk.page_number || 1}</span>
                      </div>

                      <div className="p-3.5 rounded bg-[#0c1421] border border-[#26364a] text-xs font-mono text-[#cbd5e1] leading-relaxed whitespace-pre-wrap max-h-72 overflow-y-auto">
                        {activeInspectedChunk.text}
                      </div>

                      <div className="p-2.5 rounded bg-[#18202d] border border-[#26364a] flex items-center justify-between text-[11px] font-mono text-[#8d98b0]">
                        <span>Char Offsets: [{activeInspectedChunk.char_start ?? 0} - {activeInspectedChunk.char_end ?? activeInspectedChunk.text.length}]</span>
                        <span className="text-emerald-400 flex items-center gap-1">
                          <span className="material-symbols-outlined text-[14px]">check</span> Hash Grounded
                        </span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-[#8d98b0] py-6 text-center">
                      Click on any chunk citation pill (e.g. chunk_1) to inspect its exact source passage.
                    </p>
                  )}

                  {/* All Chunks Selector */}
                  <div className="mt-4 pt-3 border-t border-[#26364a]">
                    <span className="text-[11px] font-mono uppercase text-[#8d98b0] block mb-2">Available Source Chunks:</span>
                    <div className="flex flex-wrap gap-1.5">
                      {structuredModel.source_chunks.map((c) => (
                        <button
                          key={c.chunk_id}
                          type="button"
                          onClick={() => setActiveInspectedChunk(c)}
                          className={`citation-pill ${activeInspectedChunk?.chunk_id === c.chunk_id ? 'selected' : ''}`}
                        >
                          {c.chunk_id}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STAGE 3: CONFIGURE (TARGET AUDIENCE & ARTEFACTS) */}
        {/* ======================================================== */}
        {currentStage === 3 && structuredModel && (
          <div className="max-w-4xl w-full mx-auto flex flex-col gap-6">
            <div className="flex flex-col items-center text-center gap-2">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#18202d] text-blue-400 font-mono text-xs uppercase tracking-wider border border-[#26364a]">
                Stage 3 of 5 · Transformation Engine
              </div>
              <h2 className="text-3xl font-bold text-white tracking-tight">
                Configure Output Deliverables
              </h2>
              <p className="text-sm text-[#8d98b0] max-w-xl">
                Select target audiences and communicative objectives. Info2Impact derives each deliverable from the canonical model without re-running document analysis.
              </p>
            </div>

            <div className="command-card p-6 sm:p-8 flex flex-col gap-6">
              {/* Sliders / Selectors */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-mono uppercase text-[#8d98b0]">Target Audience</label>
                  <select
                    className="w-full bg-[#141c29] text-white p-2.5 rounded border border-[#26364a] focus:border-blue-500 text-sm"
                    value={config.audience}
                    onChange={(e) => setConfig({ ...config, audience: e.target.value as Audience })}
                  >
                    <option value="executive">Executive</option>
                    <option value="technical">Technical</option>
                    <option value="general_public">General Public</option>
                    <option value="analyst">Analyst</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-mono uppercase text-[#8d98b0]">Linguistic Tone</label>
                  <select
                    className="w-full bg-[#141c29] text-white p-2.5 rounded border border-[#26364a] focus:border-blue-500 text-sm"
                    value={config.tone}
                    onChange={(e) => setConfig({ ...config, tone: e.target.value as Tone })}
                  >
                    <option value="professional">Professional</option>
                    <option value="formal">Formal</option>
                    <option value="informative">Informative</option>
                    <option value="concise">Concise</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-mono uppercase text-[#8d98b0]">Detail Level</label>
                  <select
                    className="w-full bg-[#141c29] text-white p-2.5 rounded border border-[#26364a] focus:border-blue-500 text-sm"
                    value={config.detail_level}
                    onChange={(e) => setConfig({ ...config, detail_level: e.target.value as DetailLevel })}
                  >
                    <option value="standard">Standard</option>
                    <option value="brief">Brief</option>
                    <option value="detailed">Detailed</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-mono uppercase text-[#8d98b0]">Objective</label>
                  <select
                    className="w-full bg-[#141c29] text-white p-2.5 rounded border border-[#26364a] focus:border-blue-500 text-sm"
                    value={config.objective}
                    onChange={(e) => setConfig({ ...config, objective: e.target.value as Objective })}
                  >
                    <option value="inform">Inform</option>
                    <option value="brief">Brief</option>
                    <option value="summarize">Summarize</option>
                    <option value="communicate">Communicate</option>
                  </select>
                </div>
              </div>

              {/* Target Deliverables Checkboxes */}
              <div className="flex flex-col gap-3 pt-4 border-t border-[#26364a]">
                <span className="text-xs font-mono uppercase text-[#8d98b0]">Select Output Artefacts:</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    { id: 'executive_summary', title: 'Executive Summary', desc: 'High-level findings, risk matrices, and strategic directives for command staff.' },
                    { id: 'advisory_brief', title: 'Advisory Brief', desc: 'Rigorous technical observations, threat exposures, and operator instructions.' },
                    { id: 'public_communication', title: 'Public Communication', desc: 'Accessible, jargon-free announcements and public safety advisories.' },
                    { id: 'presentation', title: 'Presentation Outline', desc: 'Slide-by-slide executive briefing deck with data highlights and speaker notes.' }
                  ].map((item) => (
                    <label
                      key={item.id}
                      className={`p-4 rounded-lg border transition-all cursor-pointer flex items-start gap-3 ${
                        selectedOutputs.includes(item.id as OutputType)
                          ? 'bg-[#1a2638] border-blue-500 shadow-sm'
                          : 'bg-[#141c29] border-[#26364a] hover:border-[#384a64]'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedOutputs.includes(item.id as OutputType)}
                        onChange={() => toggleOutputType(item.id as OutputType)}
                        className="mt-1 accent-blue-600 rounded"
                      />
                      <div className="flex flex-col">
                        <span className="text-sm font-bold text-white">{item.title}</span>
                        <span className="text-xs text-[#8d98b0] mt-0.5">{item.desc}</span>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {transformError && (
                <div className="p-4 rounded-lg bg-red-950/40 border border-red-700/50 text-red-300 text-sm">
                  {transformError}
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center justify-between pt-2">
                <button
                  type="button"
                  onClick={() => setCurrentStage(2)}
                  className="btn-command btn-secondary-command"
                >
                  <span className="material-symbols-outlined text-[18px]">arrow_back</span>
                  Back to Understanding
                </button>

                <button
                  type="button"
                  onClick={handleTransform}
                  disabled={isTransforming || selectedOutputs.length === 0}
                  className="btn-command btn-primary-command"
                >
                  <span>Generate Selected Outputs ({selectedOutputs.length})</span>
                  <span className="material-symbols-outlined text-[18px]">auto_awesome</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STAGE 4: GENERATION LOADING TELEMETRY */}
        {/* ======================================================== */}
        {currentStage === 4 && (
          <div className="max-w-2xl w-full mx-auto py-16 flex flex-col items-center text-center gap-6">
            <div className="w-20 h-20 rounded-2xl bg-[#18202d] border border-blue-500/40 flex items-center justify-center text-blue-400 shadow-2xl relative">
              <span className="w-20 h-20 rounded-2xl border-2 border-blue-500/20 border-t-blue-500 animate-spin absolute inset-0"></span>
              <span className="material-symbols-outlined text-[36px] animate-pulse">model_training</span>
            </div>

            <div className="flex flex-col gap-2">
              <span className="text-xs font-mono uppercase tracking-wider text-blue-400">
                Stage 4 of 5 · Multi-Output Orchestration
              </span>
              <h2 className="text-2xl font-bold text-white">Synthesizing Verified Artefacts</h2>
              <p className="text-sm text-[#8d98b0] max-w-md">{generationProgress}</p>
            </div>

            <div className="w-full bg-[#141c29] p-4 rounded-xl border border-[#26364a] text-xs font-mono text-[#8d98b0] flex flex-col gap-2 text-left">
              <div className="flex items-center gap-2 text-emerald-400">
                <span className="material-symbols-outlined text-[14px]">check</span>
                Canonical model locked (0 re-analysis passes)
              </div>
              <div className="flex items-center gap-2 text-blue-400">
                <span className="material-symbols-outlined text-[14px]">sync</span>
                Orchestrating {selectedOutputs.join(', ')}...
              </div>
              <div className="flex items-center gap-2 text-[#64748b]">
                <span className="material-symbols-outlined text-[14px]">shield</span>
                Running deterministic claim-to-chunk grounding audit...
              </div>
            </div>
          </div>
        )}

        {/* ======================================================== */}
        {/* STAGE 5: REVIEW & MULTI-ARTEFACT DISPLAY */}
        {/* ======================================================== */}
        {currentStage === 5 && transformResults && (
          <div className="flex flex-col gap-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 text-emerald-400 font-mono text-xs uppercase tracking-wider mb-1">
                  <span className="material-symbols-outlined text-[15px]">verified</span>
                  <span>Stage 5 of 5 · Review & Deliverables</span>
                </div>
                <h2 className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                  Generated Communication Artefacts
                </h2>
                <p className="text-sm text-[#8d98b0]">
                  Grounded across {selectedOutputs.length} purpose-tailored formats from a single factual extraction.
                </p>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setCurrentStage(3)}
                  className="btn-command btn-secondary-command text-xs py-2 px-3"
                >
                  <span className="material-symbols-outlined text-[16px]">tune</span>
                  Adjust Parameters
                </button>
                <button
                  type="button"
                  onClick={handleResetAll}
                  className="btn-command btn-primary-command text-xs py-2 px-3"
                >
                  <span className="material-symbols-outlined text-[16px]">add_circle</span>
                  New Ingestion
                </button>
              </div>
            </div>

            {/* Artefacts Tab Bar */}
            <div className="flex items-center gap-2 border-b border-[#26364a] overflow-x-auto pb-1">
              {transformResults.executive_summary && (
                <button
                  type="button"
                  className={`toggle-tab text-sm ${activeOutputTab === 'executive_summary' ? 'active' : ''}`}
                  onClick={() => setActiveOutputTab('executive_summary')}
                >
                  📊 Executive Summary
                </button>
              )}
              {transformResults.advisory_brief && (
                <button
                  type="button"
                  className={`toggle-tab text-sm ${activeOutputTab === 'advisory_brief' ? 'active' : ''}`}
                  onClick={() => setActiveOutputTab('advisory_brief')}
                >
                  🛡️ Advisory Brief
                </button>
              )}
              {transformResults.public_communication && (
                <button
                  type="button"
                  className={`toggle-tab text-sm ${activeOutputTab === 'public_communication' ? 'active' : ''}`}
                  onClick={() => setActiveOutputTab('public_communication')}
                >
                  📢 Public Release
                </button>
              )}
              {transformResults.presentation && (
                <button
                  type="button"
                  className={`toggle-tab text-sm ${activeOutputTab === 'presentation' ? 'active' : ''}`}
                  onClick={() => setActiveOutputTab('presentation')}
                >
                  📑 Presentation Outline
                </button>
              )}
            </div>

            {/* Artefact Content Body */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Main Content Area (8 cols) */}
              <div className="lg:col-span-8 flex flex-col gap-6">
                
                {/* 1. Executive Summary Tab */}
                {activeOutputTab === 'executive_summary' && transformResults.executive_summary && (
                  <div className="command-card p-6 sm:p-8 flex flex-col gap-6">
                    <div>
                      <span className="text-xs font-mono uppercase text-blue-400 block mb-1">Executive Briefing</span>
                      <h3 className="text-2xl font-bold text-white mb-3">{transformResults.executive_summary.title}</h3>
                      <p className="text-sm text-[#cbd5e1] leading-relaxed bg-[#141c29] p-4 rounded-lg border border-[#26364a]">
                        {transformResults.executive_summary.overview}
                      </p>
                    </div>

                    <div className="flex flex-col gap-3">
                      <h4 className="text-xs font-mono uppercase text-[#8d98b0] tracking-wider">Key Strategic Findings</h4>
                      <ul className="flex flex-col gap-2">
                        {transformResults.executive_summary.key_findings.map((f, i) => (
                          <li key={i} className="text-sm text-[#dbe2f5] flex items-start gap-2 bg-[#141c29] p-3 rounded border border-[#26364a]">
                            <span className="material-symbols-outlined text-blue-400 text-[18px] shrink-0">check_circle</span>
                            <span>{f}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    {transformResults.executive_summary.risks_implications.length > 0 && (
                      <div className="flex flex-col gap-3">
                        <h4 className="text-xs font-mono uppercase text-amber-400 tracking-wider">Risks & Strategic Implications</h4>
                        <ul className="flex flex-col gap-2">
                          {transformResults.executive_summary.risks_implications.map((r, i) => (
                            <li key={i} className="text-xs text-amber-200 bg-amber-950/20 border border-amber-900/40 p-3 rounded">
                              {r}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {transformResults.executive_summary.recommended_actions.length > 0 && (
                      <div className="flex flex-col gap-3">
                        <h4 className="text-xs font-mono uppercase text-emerald-400 tracking-wider">Recommended Action Directives</h4>
                        <ul className="flex flex-col gap-2">
                          {transformResults.executive_summary.recommended_actions.map((a, i) => (
                            <li key={i} className="text-xs text-emerald-200 bg-emerald-950/20 border border-emerald-900/40 p-3 rounded font-medium">
                              {a}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}

                {/* 2. Advisory Brief Tab */}
                {activeOutputTab === 'advisory_brief' && transformResults.advisory_brief && (
                  <div className="command-card p-6 sm:p-8 flex flex-col gap-6">
                    <div>
                      <span className="text-xs font-mono uppercase text-emerald-400 block mb-1">Technical Incident Directive</span>
                      <h3 className="text-2xl font-bold text-white mb-3">{transformResults.advisory_brief.title}</h3>
                      <p className="text-sm text-[#cbd5e1] leading-relaxed bg-[#141c29] p-4 rounded-lg border border-[#26364a]">
                        {transformResults.advisory_brief.situation_context}
                      </p>
                    </div>

                    <div className="flex flex-col gap-3">
                      <h4 className="text-xs font-mono uppercase text-[#8d98b0] tracking-wider">Key Technical Observations</h4>
                      <ul className="flex flex-col gap-2">
                        {transformResults.advisory_brief.key_observations.map((obs, i) => (
                          <li key={i} className="text-sm text-[#dbe2f5] bg-[#141c29] p-3 rounded border border-[#26364a]">
                            {obs}
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="p-4 rounded-lg bg-red-950/20 border border-red-800/40">
                      <h4 className="text-xs font-mono uppercase text-red-400 tracking-wider mb-1">Threat Exposure & Impact</h4>
                      <p className="text-sm text-red-200">{transformResults.advisory_brief.risk_impact}</p>
                    </div>

                    <div className="flex flex-col gap-3">
                      <h4 className="text-xs font-mono uppercase text-emerald-400 tracking-wider">Mandatory Directives</h4>
                      <ul className="flex flex-col gap-2">
                        {transformResults.advisory_brief.recommended_actions_directives.map((d, i) => (
                          <li key={i} className="text-xs text-emerald-300 font-semibold bg-emerald-950/20 border border-emerald-900/40 p-3 rounded">
                            {d}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}

                {/* 3. Public Communication Tab */}
                {activeOutputTab === 'public_communication' && transformResults.public_communication && (
                  <div className="command-card p-6 sm:p-8 flex flex-col gap-6">
                    <div>
                      <span className="text-xs font-mono uppercase text-blue-400 block mb-1">Public Release</span>
                      <h3 className="text-2xl font-bold text-white mb-3">{transformResults.public_communication.headline}</h3>
                      <p className="text-sm text-[#cbd5e1] leading-relaxed">{transformResults.public_communication.opening}</p>
                    </div>

                    <div className="p-5 rounded-xl bg-blue-950/30 border border-blue-700/40">
                      <span className="text-xs font-mono uppercase text-blue-300 block mb-1 font-bold">Core Message</span>
                      <p className="text-base text-white font-medium leading-snug">
                        {transformResults.public_communication.core_message}
                      </p>
                    </div>

                    <div className="flex flex-col gap-2">
                      <h4 className="text-xs font-mono uppercase text-[#8d98b0] tracking-wider">Plain-Language Context</h4>
                      <p className="text-sm text-[#dbe2f5] bg-[#141c29] p-4 rounded border border-[#26364a] leading-relaxed">
                        {transformResults.public_communication.explanation}
                      </p>
                    </div>

                    <div className="p-4 rounded-lg bg-emerald-950/20 border border-emerald-800/40">
                      <span className="text-xs font-mono uppercase text-emerald-400 block mb-1 font-bold">Citizen Guidance & Assurance</span>
                      <p className="text-sm text-emerald-200">{transformResults.public_communication.public_guidance}</p>
                    </div>
                  </div>
                )}

                {/* 4. Presentation Outline Tab */}
                {activeOutputTab === 'presentation' && transformResults.presentation && (
                  <div className="command-card p-6 sm:p-8 flex flex-col gap-6">
                    <div>
                      <span className="text-xs font-mono uppercase text-indigo-400 block mb-1">Briefing Slide Deck</span>
                      <h3 className="text-2xl font-bold text-white mb-4">{transformResults.presentation.presentation_title}</h3>
                    </div>

                    <div className="flex flex-col gap-4">
                      {transformResults.presentation.slides.map((slide) => (
                        <div key={slide.slide_number} className="slide-preview-card flex flex-col gap-3">
                          <div className="flex items-center justify-between border-b border-[#26364a] pb-2">
                            <div className="flex items-center gap-2">
                              <span className="w-6 h-6 rounded bg-blue-500/20 text-blue-400 font-mono text-xs flex items-center justify-center font-bold">
                                {slide.slide_number}
                              </span>
                              <h4 className="text-sm font-bold text-white">{slide.title}</h4>
                            </div>
                            {slide.data_highlights && (
                              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-indigo-900/40 text-indigo-300 border border-indigo-700/40">
                                {slide.data_highlights}
                              </span>
                            )}
                          </div>

                          <ul className="flex flex-col gap-1.5 pl-2">
                            {slide.key_points.map((pt, i) => (
                              <li key={i} className="text-xs text-[#cbd5e1] list-disc list-inside">
                                {pt}
                              </li>
                            ))}
                          </ul>

                          <div className="speaker-note-box">
                            <span className="block text-[11px] font-bold uppercase tracking-wider mb-0.5">Speaker Guidance:</span>
                            {slide.speaker_notes}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Right Column: Source Provenance & Citations Inspector (4 cols) */}
              <div className="lg:col-span-4 sticky top-20">
                <div className="command-card p-5 bg-[#141c29]">
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#26364a]">
                    <div className="flex items-center gap-2 text-blue-400 font-mono text-xs uppercase font-bold">
                      <span className="material-symbols-outlined text-[18px]">verified</span>
                      <span>Grounding Citations</span>
                    </div>
                    <span className="text-[11px] font-mono text-emerald-400">100% Traceable</span>
                  </div>

                  {/* Extract active citations */}
                  <div className="flex flex-col gap-2.5 max-h-96 overflow-y-auto">
                    {(() => {
                      let activeRefs: any[] = [];
                      if (activeOutputTab === 'executive_summary') activeRefs = transformResults.executive_summary?.source_references || [];
                      else if (activeOutputTab === 'advisory_brief') activeRefs = transformResults.advisory_brief?.source_references || [];
                      else if (activeOutputTab === 'public_communication') activeRefs = transformResults.public_communication?.source_references || [];
                      else if (activeOutputTab === 'presentation') activeRefs = transformResults.presentation?.source_references || [];

                      return activeRefs.map((ref, idx) => (
                        <div
                          key={idx}
                          onClick={() => selectChunkById(ref.source_chunk_id)}
                          className="p-3 rounded bg-[#0c1421] border border-[#26364a] hover:border-blue-500/50 cursor-pointer transition-colors"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="citation-pill font-mono text-[11px]">{ref.source_chunk_id}</span>
                            <span className="text-[10px] text-[#64748b] font-mono">Click to view source</span>
                          </div>
                          <p className="text-xs text-[#dbe2f5]">{ref.claim}</p>
                          {ref.source_snippet && (
                            <p className="text-[11px] text-[#8d98b0] mt-1 italic border-l-2 border-blue-500/40 pl-2">
                              "{ref.source_snippet}"
                            </p>
                          )}
                        </div>
                      ));
                    })()}
                  </div>

                  {activeInspectedChunk && (
                    <div className="mt-4 pt-3 border-t border-[#26364a] flex flex-col gap-2">
                      <span className="text-[11px] font-mono uppercase text-blue-400">
                        Inspected Chunk: {activeInspectedChunk.chunk_id}
                      </span>
                      <p className="text-xs font-mono text-[#94a3b8] bg-[#0c1421] p-2.5 rounded max-h-32 overflow-y-auto">
                        {activeInspectedChunk.text}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default App;
