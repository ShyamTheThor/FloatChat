import React, { useState, useRef, useEffect } from 'react';
import { Send, Map as MapIcon, LineChart, Loader2 } from 'lucide-react';
import './App.css';

import MapViewer from './components/MapViewer';
import ChartViewer from './components/ChartViewer';

function App() {
  const [messages, setMessages] = useState([
    { role: 'bot', content: "Hello! I'm FloatChat. Ask me anything about ARGO ocean data (e.g. 'Show me salinity in the Arabian Sea')." }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [data, setData] = useState([]);
  const [plotType, setPlotType] = useState('none'); // 'map', 'time_series', 'depth_profile', 'none'
  const [activeVis, setActiveVis] = useState('map');

  const messagesEndRef = useRef(null);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Set default vis tab based on what backend recommends
  useEffect(() => {
    if (plotType !== 'none') {
      if (plotType === 'map') setActiveVis('map');
      else setActiveVis('chart');
    }
  }, [plotType]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage })
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const resData = await response.json();
      
      setMessages(prev => [...prev, { role: 'bot', content: resData.answer }]);
      if (resData.data && resData.data.length > 0) {
        setData(resData.data);
      }
      setPlotType(resData.plot_type);

    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { role: 'bot', content: "Sorry, there was an error processing your request." }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Sidebar Chat */}
      <div className="chat-container">
        <div className="chat-header">
          <h1>🌊 FloatChat</h1>
        </div>
        
        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              {msg.content}
            </div>
          ))}
          {isLoading && (
            <div className="message bot" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <Loader2 className="animate-spin" size={16} /> Thinking...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        
        <div className="chat-input-container">
          <form onSubmit={handleSubmit} className="chat-form">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask about ocean conditions..."
              className="chat-input"
              disabled={isLoading}
            />
            <button type="submit" className="send-button" disabled={!input.trim() || isLoading}>
              <Send size={18} />
            </button>
          </form>
        </div>
      </div>

      {/* Main Visualization Area */}
      <div className="vis-container">
        <div className="vis-header">
          <button 
            className={`vis-toggle ${activeVis === 'map' ? 'active' : ''}`}
            onClick={() => setActiveVis('map')}
          >
            <MapIcon size={18} /> Map View
          </button>
          <button 
            className={`vis-toggle ${activeVis === 'chart' ? 'active' : ''}`}
            onClick={() => setActiveVis('chart')}
          >
            <LineChart size={18} /> Charts
          </button>
        </div>

        <div className="vis-content">
          {data.length === 0 ? (
            <div className="empty-state">
              <MapIcon size={48} />
              <h2>No data to visualize yet</h2>
              <p>Ask a question to see ocean ARGO floats plotted here.</p>
            </div>
          ) : activeVis === 'map' ? (
            <MapViewer data={data} />
          ) : (
            <ChartViewer data={data} plotType={plotType} />
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
