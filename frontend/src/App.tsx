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
  Objective
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

export const App: React.FC = () => {
  // Connection State
  const [healthStatus, setHealthStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);

  // Ingestion & Analysis State
  const [inputMode, setInputMode] = useState<'text' | 'file'>('text');
  const [sourceText, setSourceText] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [structuredModel, setStructuredModel] = useState<StructuredContentModel | null>(null);
  const [analysisError, setAnalysisError] = useState<string>('');

  // Transformation Configuration State
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

  // Transformation Results State
  const [isTransforming, setIsTransforming] = useState<boolean>(false);
  const [transformResults, setTransformResults] = useState<MultiTransformResponse | null>(null);
  const [activeOutputTab, setActiveOutputTab] = useState<OutputType>('executive_summary');
  const [transformError, setTransformError] = useState<string>('');

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

  const handleLoadSample = () => {
    setInputMode('text');
    setSourceText(SAMPLE_TEXT);
    setAnalysisError('');
  };

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setAnalysisError('');
    setStructuredModel(null);
    setTransformResults(null);

    try {
      if (inputMode === 'file' && selectedFile) {
        // Upload & chunk file, then analyze
        const ingestRes = await uploadSourceFile(selectedFile);
        const model = await analyzeSource({ chunks: ingestRes.chunks });
        setStructuredModel(model);
      } else {
        if (!sourceText.trim() || sourceText.trim().length < 10) {
          throw new Error('Please provide at least 10 characters of source text.');
        }
        const model = await analyzeSource({ source_text: sourceText.trim() });
        setStructuredModel(model);
      }
    } catch (err: any) {
      setAnalysisError(err.message || 'Analysis failed.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleOutputType = (type: OutputType) => {
    setSelectedOutputs((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const handleTransform = async () => {
    if (!structuredModel) return;
    if (selectedOutputs.length === 0) {
      setTransformError('Please select at least one output artefact to generate.');
      return;
    }

    setIsTransforming(true);
    setTransformError('');

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
    } catch (err: any) {
      setTransformError(err.message || 'Transformation failed.');
    } finally {
      setIsTransforming(false);
    }
  };

  return (
    <div className="container">
      {/* Header Banner */}
      <header className="header-banner">
        <div className="header-title">
          <h1>TransformAI</h1>
          <p>Gen AI Platform for Automated Content Transformation • SIH26154 / NTRO</p>
        </div>
        <div>
          <span
            className={`status-badge ${
              healthStatus === 'connected'
                ? 'status-connected'
                : healthStatus === 'disconnected'
                ? 'status-disconnected'
                : 'status-checking'
            }`}
          >
            ● Backend {healthStatus === 'connected' ? `Online (${healthData?.service || 'Qwen3:8B'})` : healthStatus}
          </span>
        </div>
      </header>

      {/* Step 1: Ingestion & Canonical Analysis */}
      <section className="card">
        <h2 className="card-title">
          <span className="step-pill">Step 1</span>
          Source Document Ingestion & Canonical Analysis
        </h2>

        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
          <button
            type="button"
            className={`btn ${inputMode === 'text' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setInputMode('text')}
          >
            Pasted Text
          </button>
          <button
            type="button"
            className={`btn ${inputMode === 'file' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setInputMode('file')}
          >
            Upload File (TXT / PDF)
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ marginLeft: 'auto' }}
            onClick={handleLoadSample}
          >
            Load Sample Incident Dossier
          </button>
        </div>

        {inputMode === 'text' ? (
          <div className="form-group">
            <label className="form-label">Source Material Text:</label>
            <textarea
              className="form-control"
              rows={8}
              placeholder="Paste authoritative technical reports, policy directives, or incident advisories..."
              value={sourceText}
              onChange={(e) => setSourceText(e.target.value)}
            />
          </div>
        ) : (
          <div className="form-group">
            <label className="form-label">Select Document (.txt or .pdf):</label>
            <input
              type="file"
              accept=".txt,.pdf"
              className="form-control"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
            />
            {selectedFile && (
              <p style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.4rem' }}>
                Selected: <strong>{selectedFile.name}</strong> ({(selectedFile.size / 1024).toFixed(1)} KB)
              </p>
            )}
          </div>
        )}

        {analysisError && (
          <div style={{ padding: '0.75rem 1rem', backgroundColor: '#fee2e2', color: '#b91c1c', borderRadius: '8px', marginBottom: '1rem' }}>
            <strong>Analysis Error:</strong> {analysisError}
          </div>
        )}

        <button
          type="button"
          className="btn btn-primary"
          onClick={handleAnalyze}
          disabled={isAnalyzing || (inputMode === 'text' && !sourceText.trim()) || (inputMode === 'file' && !selectedFile)}
        >
          {isAnalyzing ? 'Extracting Canonical Factual Model...' : 'Analyze & Extract Canonical Model'}
        </button>
      </section>

      {/* Step 2: Canonical Structured Content Model View */}
      {structuredModel && (
        <section className="card" style={{ borderColor: '#3b82f6', backgroundColor: '#fcfdff' }}>
          <h2 className="card-title">
            <span className="step-pill" style={{ backgroundColor: '#0284c7' }}>Canonical</span>
            Extracted Structured Content Model (Single Source of Truth)
          </h2>

          <div style={{ marginBottom: '1rem' }}>
            <h3 style={{ margin: '0 0 0.4rem 0', fontSize: '1.1rem', color: '#1e3a8a' }}>{structuredModel.topic}</h3>
            <p style={{ color: '#334155', fontSize: '0.95rem', margin: 0 }}>{structuredModel.summary}</p>
          </div>

          <div className="grid-2">
            <div style={{ background: '#ffffff', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <h4 style={{ margin: '0 0 0.5rem 0', color: '#1e293b' }}>Verified Key Facts:</h4>
              <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
                {structuredModel.key_facts.map((f) => (
                  <li key={f.fact_id} style={{ marginBottom: '0.4rem' }}>
                    {f.source_chunk_ids.map((cid) => (
                      <span key={cid} className="chunk-badge">{cid}</span>
                    ))}
                    {f.statement}
                  </li>
                ))}
              </ul>
            </div>

            <div style={{ background: '#ffffff', padding: '1rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
              <h4 style={{ margin: '0 0 0.5rem 0', color: '#1e293b' }}>Key Metrics & Directives:</h4>
              <ul style={{ margin: 0, paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
                {structuredModel.metrics.map((m, idx) => (
                  <li key={idx} style={{ marginBottom: '0.4rem' }}>
                    <strong>{m.metric}:</strong> {m.value}
                  </li>
                ))}
                {structuredModel.recommendations.map((r, idx) => (
                  <li key={idx} style={{ marginBottom: '0.4rem', color: '#15803d' }}>
                    <strong>Action:</strong> {r.action}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div style={{ marginTop: '1rem', fontSize: '0.85rem', color: '#64748b' }}>
            Available Source Chunks: {structuredModel.source_chunks.map((c) => (
              <span key={c.chunk_id} className="chunk-badge">{c.chunk_id}</span>
            ))}
          </div>
        </section>
      )}

      {/* Step 3: Transformation Configuration & Output Selection */}
      {structuredModel && (
        <section className="card">
          <h2 className="card-title">
            <span className="step-pill">Step 2</span>
            Transformation Configuration & Target Outputs
          </h2>

          <div className="grid-4" style={{ marginBottom: '1.5rem' }}>
            <div className="form-group">
              <label className="form-label">Target Audience:</label>
              <select
                className="form-control"
                value={config.audience}
                onChange={(e) => setConfig({ ...config, audience: e.target.value as Audience })}
              >
                <option value="executive">Executive</option>
                <option value="technical">Technical</option>
                <option value="general_public">General Public</option>
                <option value="analyst">Analyst</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Tone:</label>
              <select
                className="form-control"
                value={config.tone}
                onChange={(e) => setConfig({ ...config, tone: e.target.value as Tone })}
              >
                <option value="professional">Professional</option>
                <option value="formal">Formal</option>
                <option value="informative">Informative</option>
                <option value="concise">Concise</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Detail Level:</label>
              <select
                className="form-control"
                value={config.detail_level}
                onChange={(e) => setConfig({ ...config, detail_level: e.target.value as DetailLevel })}
              >
                <option value="standard">Standard</option>
                <option value="brief">Brief</option>
                <option value="detailed">Detailed</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Objective:</label>
              <select
                className="form-control"
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

          <div className="form-group">
            <label className="form-label">Select Output Artefacts to Generate:</label>
            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={selectedOutputs.includes('executive_summary')}
                  onChange={() => toggleOutputType('executive_summary')}
                />
                <strong>Executive Summary</strong>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={selectedOutputs.includes('advisory_brief')}
                  onChange={() => toggleOutputType('advisory_brief')}
                />
                <strong>Advisory Brief</strong>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={selectedOutputs.includes('public_communication')}
                  onChange={() => toggleOutputType('public_communication')}
                />
                <strong>Public Communication</strong>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={selectedOutputs.includes('presentation')}
                  onChange={() => toggleOutputType('presentation')}
                />
                <strong>Presentation Outline</strong>
              </label>
            </div>
          </div>

          {transformError && (
            <div style={{ padding: '0.75rem 1rem', backgroundColor: '#fee2e2', color: '#b91c1c', borderRadius: '8px', marginBottom: '1rem' }}>
              <strong>Transformation Error:</strong> {transformError}
            </div>
          )}

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleTransform}
            disabled={isTransforming || selectedOutputs.length === 0}
          >
            {isTransforming ? 'Orchestrating Transformations...' : 'Generate Selected Outputs'}
          </button>
        </section>
      )}

      {/* Step 4: Transformed Multi-Output Results Display */}
      {transformResults && (
        <section className="card">
          <h2 className="card-title">
            <span className="step-pill" style={{ backgroundColor: '#16a34a' }}>Generated</span>
            Transformed Communication Artefacts
          </h2>

          <nav className="tab-nav">
            {transformResults.executive_summary && (
              <button
                type="button"
                className={`tab-btn ${activeOutputTab === 'executive_summary' ? 'active' : ''}`}
                onClick={() => setActiveOutputTab('executive_summary')}
              >
                Executive Summary
              </button>
            )}
            {transformResults.advisory_brief && (
              <button
                type="button"
                className={`tab-btn ${activeOutputTab === 'advisory_brief' ? 'active' : ''}`}
                onClick={() => setActiveOutputTab('advisory_brief')}
              >
                Advisory Brief
              </button>
            )}
            {transformResults.public_communication && (
              <button
                type="button"
                className={`tab-btn ${activeOutputTab === 'public_communication' ? 'active' : ''}`}
                onClick={() => setActiveOutputTab('public_communication')}
              >
                Public Communication
              </button>
            )}
            {transformResults.presentation && (
              <button
                type="button"
                className={`tab-btn ${activeOutputTab === 'presentation' ? 'active' : ''}`}
                onClick={() => setActiveOutputTab('presentation')}
              >
                Presentation Outline
              </button>
            )}
          </nav>

          {/* Executive Summary Tab Content */}
          {activeOutputTab === 'executive_summary' && transformResults.executive_summary && (
            <div>
              <h3 style={{ margin: '0 0 1rem 0', color: '#1e40af' }}>{transformResults.executive_summary.title}</h3>
              
              <div className="output-section">
                <h4>Strategic Overview</h4>
                <p>{transformResults.executive_summary.overview}</p>
              </div>

              <div className="output-section">
                <h4>Key Strategic Findings</h4>
                <ul>
                  {transformResults.executive_summary.key_findings.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>

              {transformResults.executive_summary.risks_implications.length > 0 && (
                <div className="output-section">
                  <h4>Risks & Implications</h4>
                  <ul>
                    {transformResults.executive_summary.risks_implications.map((r, i) => (
                      <li key={i} style={{ color: '#b91c1c' }}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {transformResults.executive_summary.recommended_actions.length > 0 && (
                <div className="output-section">
                  <h4>Recommended Directives</h4>
                  <ul>
                    {transformResults.executive_summary.recommended_actions.map((a, i) => (
                      <li key={i} style={{ color: '#15803d' }}><strong>{a}</strong></li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="output-section" style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
                <h4>Source Grounding Citations</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {transformResults.executive_summary.source_references.map((ref, idx) => (
                    <div key={idx} style={{ fontSize: '0.85rem', color: '#475569' }}>
                      <span className="citation-tag">{ref.source_chunk_id}</span> {ref.claim}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Advisory Brief Tab Content */}
          {activeOutputTab === 'advisory_brief' && transformResults.advisory_brief && (
            <div>
              <h3 style={{ margin: '0 0 1rem 0', color: '#0f766e' }}>{transformResults.advisory_brief.title}</h3>
              
              <div className="output-section">
                <h4>Situation Context</h4>
                <p>{transformResults.advisory_brief.situation_context}</p>
              </div>

              <div className="output-section">
                <h4>Key Technical Observations</h4>
                <ul>
                  {transformResults.advisory_brief.key_observations.map((o, i) => (
                    <li key={i}>{o}</li>
                  ))}
                </ul>
              </div>

              <div className="output-section">
                <h4>Threat Impact & Exposure</h4>
                <p style={{ color: '#b91c1c', fontWeight: 500 }}>{transformResults.advisory_brief.risk_impact}</p>
              </div>

              <div className="output-section">
                <h4>Mandatory Action Directives</h4>
                <ul>
                  {transformResults.advisory_brief.recommended_actions_directives.map((d, i) => (
                    <li key={i} style={{ color: '#15803d' }}><strong>{d}</strong></li>
                  ))}
                </ul>
              </div>

              {transformResults.advisory_brief.caveats.length > 0 && (
                <div className="output-section">
                  <h4>Operational Caveats & Boundaries</h4>
                  <ul>
                    {transformResults.advisory_brief.caveats.map((c, i) => (
                      <li key={i} style={{ color: '#64748b' }}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="output-section" style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
                <h4>Source Grounding Citations</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {transformResults.advisory_brief.source_references.map((ref, idx) => (
                    <div key={idx} style={{ fontSize: '0.85rem', color: '#475569' }}>
                      <span className="citation-tag">{ref.source_chunk_id}</span> {ref.claim}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Public Communication Tab Content */}
          {activeOutputTab === 'public_communication' && transformResults.public_communication && (
            <div>
              <h3 style={{ margin: '0 0 1rem 0', color: '#1e293b' }}>{transformResults.public_communication.headline}</h3>
              
              <div className="output-section">
                <h4>Opening Context</h4>
                <p>{transformResults.public_communication.opening}</p>
              </div>

              <div className="output-section" style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', borderLeft: '4px solid #3b82f6' }}>
                <h4 style={{ color: '#1e40af' }}>Core Public Message</h4>
                <p style={{ margin: 0, fontWeight: 500 }}>{transformResults.public_communication.core_message}</p>
              </div>

              <div className="output-section" style={{ marginTop: '1rem' }}>
                <h4>Plain Language Explanation</h4>
                <p>{transformResults.public_communication.explanation}</p>
              </div>

              <div className="output-section">
                <h4>Public Guidance & Status</h4>
                <p style={{ color: '#166534', fontWeight: 500 }}>{transformResults.public_communication.public_guidance}</p>
              </div>

              <div className="output-section" style={{ borderTop: '1px solid #e2e8f0', paddingTop: '1rem' }}>
                <h4>Source Grounding Citations</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  {transformResults.public_communication.source_references.map((ref, idx) => (
                    <div key={idx} style={{ fontSize: '0.85rem', color: '#475569' }}>
                      <span className="citation-tag">{ref.source_chunk_id}</span> {ref.claim}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Presentation Outline Tab Content */}
          {activeOutputTab === 'presentation' && transformResults.presentation && (
            <div>
              <h3 style={{ margin: '0 0 1rem 0', color: '#7c3aed' }}>{transformResults.presentation.presentation_title}</h3>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {transformResults.presentation.slides.map((slide) => (
                  <div key={slide.slide_number} className="slide-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                      <h4 style={{ margin: 0, color: '#1e293b' }}>
                        Slide {slide.slide_number}: {slide.title}
                      </h4>
                      {slide.data_highlights && (
                        <span style={{ fontSize: '0.8rem', background: '#e0e7ff', color: '#4338ca', padding: '0.2rem 0.5rem', borderRadius: '4px', fontWeight: 600 }}>
                          {slide.data_highlights}
                        </span>
                      )}
                    </div>

                    <ul style={{ margin: '0.5rem 0', paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
                      {slide.key_points.map((pt, i) => (
                        <li key={i}>{pt}</li>
                      ))}
                    </ul>

                    <div className="speaker-notes">
                      <strong>Presenter Script / Notes:</strong> {slide.speaker_notes}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
};

export default App;
