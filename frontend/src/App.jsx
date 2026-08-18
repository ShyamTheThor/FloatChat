import React, { useState, useRef, useEffect } from 'react';
import {
  Waves, Send, Map as MapIcon, LineChart, Loader2, RotateCcw, Download,
  Compass, Info
} from 'lucide-react';
import './App.css';

import MapViewer from './components/MapViewer';
import ChartViewer from './components/ChartViewer';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const SUGGESTED_QUERIES = [
  "Show me salinity in the Arabian Sea",
  "Show temperature in Bay of Bengal",
  "Floats at 100 meters depth",
  "Show temperature over time",
  "T-S scatter diagram"
];

function App() {
  const [messages, setMessages] = useState([
    {
      role: 'bot',
      content: "Welcome to FloatChat Oceanographic Intelligence Platform. Ask any query about ARGO float observations in the Indian Ocean."
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState([]);
  const [plotType, setPlotType] = useState('map');
  const [activeVis, setActiveVis] = useState('map');
  const [intent, setIntent] = useState(null);
  const [analytics, setAnalytics] = useState(null);

  // Metadata from backend
  const [datasetMeta, setDatasetMeta] = useState({
    status: 'connecting',
    earliest_date: null,
    latest_date: null,
    total_observations: 0,
    total_floats: 0
  });

  const messagesEndRef = useRef(null);

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Fetch dataset metadata on mount
  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/dataset/metadata`);
        if (res.ok) {
          const meta = await res.json();
          setDatasetMeta(meta);
        }
      } catch (err) {
        console.warn('Dataset metadata fetch error:', err);
      }
    };
    fetchMetadata();
  }, []);

  // Switch tab when backend specifies plot_type
  useEffect(() => {
    if (plotType && plotType !== 'none') {
      if (plotType === 'map') setActiveVis('map');
      else setActiveVis('chart');
    }
  }, [plotType]);

  const sendQuery = async (queryText) => {
    if (!queryText.trim() || isLoading) return;

    setMessages(prev => [...prev, { role: 'user', content: queryText }]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: queryText })
      });

      if (!response.ok) {
        let detailMsg = "Ocean data service is temporarily unavailable. Please verify backend API connectivity.";
        try {
          const errData = await response.json();
          if (errData?.detail) detailMsg = errData.detail;
        } catch {
          // Keep default message if response body is non-JSON
        }
        setMessages(prev => [...prev, { role: 'bot', content: detailMsg }]);
        return;
      }

      const resData = await response.json();

      setMessages(prev => [...prev, { role: 'bot', content: resData.answer }]);

      if (resData.data) {
        setData(resData.data);
      }
      if (resData.plot_type) {
        setPlotType(resData.plot_type);
      }
      if (resData.intent) {
        setIntent(resData.intent);
      }
      if (resData.analytics) {
        setAnalytics(resData.analytics);
      }

    } catch (error) {
      console.error('Fetch error:', error);
      setMessages(prev => [...prev, {
        role: 'bot',
        content: "Cannot connect to FloatChat backend API. Please ensure the server is running."
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendQuery(input);
  };

  const handleReset = () => {
    setMessages([{
      role: 'bot',
      content: "Session reset. Enter a query to analyze ARGO float data."
    }]);
    setData([]);
    setIntent(null);
    setAnalytics(null);
    setPlotType('map');
    setActiveVis('map');
  };

  const handleExportJSON = () => {
    if (!data || data.length === 0) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `floatchat_argo_export_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
  };

  return (
    <div className="dashboard-root">
      {/* Top Header Navigation */}
      <header className="top-nav">
        <div className="nav-brand">
          <Waves className="brand-icon" size={26} />
          <div>
            <span className="brand-title">FloatChat</span>
            <span className="brand-subtitle">Ocean Intelligence</span>
          </div>
        </div>

        <div className="nav-status">
          <div className="status-badge">
            <span className="status-dot"></span>
            <span>Dataset Status: Online</span>
          </div>
          {datasetMeta.earliest_date && (
            <div className="meta-info">
              Coverage: {datasetMeta.earliest_date} to {datasetMeta.latest_date} | {datasetMeta.total_floats} Floats ({datasetMeta.total_observations?.toLocaleString()} Obs)
            </div>
          )}
        </div>

        <div className="nav-actions">
          <button onClick={handleReset} className="btn-icon" title="Reset Query Session">
            <RotateCcw size={15} /> Reset
          </button>
          <button onClick={handleExportJSON} disabled={!data.length} className="btn-icon" title="Export Results JSON">
            <Download size={15} /> Export JSON
          </button>
        </div>
      </header>

      {/* Main Content Viewport */}
      <div className="main-viewport">
        {/* Left Sidebar Query & History */}
        <aside className="sidebar-panel">
          <div className="chat-history">
            {messages.map((msg, i) => (
              <div key={i} className={`chat-bubble ${msg.role}`}>
                {msg.content}
              </div>
            ))}

            {isLoading && (
              <div className="chat-bubble bot" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <Loader2 className="animate-spin" size={16} /> Parsing query & compiling SQL...
              </div>
            )}

            {/* Query Interpretation Panel for Demo Transparency */}
            {intent && !isLoading && (
              <div className="interpretation-card">
                <div className="interp-title">
                  <Info size={14} /> Query Interpreted
                </div>
                <div className="interp-grid">
                  <div className="interp-item">
                    <span className="interp-label">Region</span>
                    <span className="interp-val">{intent.region?.region_name || 'Global / Box'}</span>
                  </div>
                  <div className="interp-item">
                    <span className="interp-label">Parameter</span>
                    <span className="interp-val" style={{ textTransform: 'capitalize' }}>{intent.parameter}</span>
                  </div>
                  <div className="interp-item">
                    <span className="interp-label">Depth Range</span>
                    <span className="interp-val">
                      {intent.target_depth ? `~${intent.target_depth}m (±${intent.depth_tolerance}m)` : intent.min_depth !== null ? `${intent.min_depth}–${intent.max_depth || 'max'}m` : 'Full Water Column'}
                    </span>
                  </div>
                  <div className="interp-item">
                    <span className="interp-label">Visualization</span>
                    <span className="interp-val" style={{ textTransform: 'uppercase' }}>{intent.visualization}</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggested Query Quick Pills */}
          <div className="suggested-queries">
            {SUGGESTED_QUERIES.map((q, idx) => (
              <button key={idx} onClick={() => sendQuery(q)} className="suggest-pill" disabled={isLoading}>
                {q}
              </button>
            ))}
          </div>

          {/* Query Input */}
          <div className="input-area">
            <form onSubmit={handleSubmit} className="query-form">
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="Ask e.g. 'Show me salinity in Arabian Sea'..."
                className="query-input"
                disabled={isLoading}
              />
              <button type="submit" className="send-btn" disabled={!input.trim() || isLoading}>
                <Send size={16} />
              </button>
            </form>
          </div>
        </aside>

        {/* Central Visualization Viewport */}
        <section className="vis-viewport">
          <div className="vis-toolbar">
            <div className="tab-group">
              <button
                className={`tab-btn ${activeVis === 'map' ? 'active' : ''}`}
                onClick={() => setActiveVis('map')}
              >
                <MapIcon size={16} /> Interactive Map
              </button>
              <button
                className={`tab-btn ${activeVis === 'chart' ? 'active' : ''}`}
                onClick={() => setActiveVis('chart')}
              >
                <LineChart size={16} /> Scientific Charts
              </button>
            </div>
            {analytics && (
              <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                Showing {analytics.observation_count?.toLocaleString()} observations across {analytics.float_count} active floats
              </div>
            )}
          </div>

          <div className="vis-display">
            {data.length === 0 ? (
              <div className="empty-state">
                <Compass size={56} style={{ opacity: 0.3, color: '#06b6d4' }} />
                <h3>ARGO Ocean Data Explorer</h3>
                <p>Select a suggested query or enter a natural language question to analyze float observations.</p>
              </div>
            ) : activeVis === 'map' ? (
              <MapViewer data={data} parameter={intent?.parameter} />
            ) : (
              <ChartViewer data={data} plotType={plotType} parameter={intent?.parameter || 'all'} />
            )}
          </div>
        </section>
      </div>

      {/* Bottom KPI Statistics Summary Bar */}
      <footer className="kpi-bar">
        <div className="kpi-card">
          <span className="kpi-title">Observations</span>
          <span className="kpi-value">{analytics ? analytics.observation_count?.toLocaleString() : 0}</span>
          <span className="kpi-sub">{analytics ? `${analytics.float_count} floats` : '0 floats'}</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-title">Mean Temp</span>
          <span className="kpi-value">{analytics?.temp_mean != null ? `${analytics.temp_mean} °C` : '--'}</span>
          <span className="kpi-sub">{analytics?.temp_min != null ? `${analytics.temp_min} to ${analytics.temp_max} °C` : '--'}</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-title">Mean Salinity</span>
          <span className="kpi-value">{analytics?.sal_mean != null ? `${analytics.sal_mean} psu` : '--'}</span>
          <span className="kpi-sub">{analytics?.sal_min != null ? `${analytics.sal_min} to ${analytics.sal_max} psu` : '--'}</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-title">Depth Bounds</span>
          <span className="kpi-value">{analytics?.depth_min != null ? `${analytics.depth_min}–${analytics.depth_max} m` : '--'}</span>
          <span className="kpi-sub">Vertical column</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-title">Time Range</span>
          <span className="kpi-value" style={{ fontSize: '0.85rem' }}>{analytics?.earliest_date || '--'}</span>
          <span className="kpi-sub">{analytics?.latest_date ? `to ${analytics.latest_date}` : '--'}</span>
        </div>
      </footer>
    </div>
  );
}

export default App;

