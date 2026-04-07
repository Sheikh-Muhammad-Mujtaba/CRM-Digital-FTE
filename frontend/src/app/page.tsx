"use client";

import { useState } from 'react';

export default function App() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    message: ''
  });
  const [status, setStatus] = useState<null | 'sending' | 'success' | 'error'>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('sending');

    try {
      const response = await fetch('http://localhost:8000/api/intake/web', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_name: formData.name,
          customer_email: formData.email,
          message: formData.message,
          channel: "web"
        })
      });

      if (!response.ok) throw new Error('API Error');
      
      setStatus('success');
      setFormData({ name: '', email: '', message: '' });
      setTimeout(() => setStatus(null), 5000); // Clear success message after 5 seconds
    } catch (error) {
      console.error(error);
      setStatus('error');
      setTimeout(() => setStatus(null), 5000); // Clear error after 5 seconds
    }
  };

  return (
    <main className="min-h-screen flex flex-col items-center justify-center p-4 sm:p-8 md:p-24 relative overflow-hidden">
      {/* Background blobs optimized for responsiveness */}
      <div className="absolute top-[-20%] left-[-10%] w-72 h-72 sm:w-96 sm:h-96 bg-indigo-600/20 rounded-full mix-blend-screen filter blur-[80px] sm:blur-[100px] animate-blob" />
      <div className="absolute bottom-[-10%] right-[-20%] w-72 h-72 sm:w-96 sm:h-96 bg-purple-600/20 rounded-full mix-blend-screen filter blur-[80px] sm:blur-[100px] animate-blob animation-delay-2000" />
      

      <div className="glass-panel p-6 sm:p-8 md:p-12 rounded-2xl sm:rounded-3xl w-full max-w-2xl relative z-10 transition-all duration-300 mx-auto mt-16 sm:mt-0">
        <div className="mb-6 sm:mb-8 text-center">
          <h1 className="text-3xl sm:text-4xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-purple-400 mb-3 sm:mb-4 tracking-tight">
            Digital Support Hub
          </h1>
          <p className="text-gray-300 text-base sm:text-lg">
            How can our autonomous FTE assist you today?
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            <div className="group">
              <label className="block text-xs sm:text-sm font-medium text-gray-300 mb-1.5 sm:mb-2" htmlFor="name">
                Full Name
              </label>
              <input
                id="name"
                type="text"
                required
                className="glass-input w-full px-3 py-2.5 sm:px-4 sm:py-3 rounded-lg sm:rounded-xl text-sm sm:text-base focus:ring-2 focus:ring-indigo-500/50"
                value={formData.name}
                onChange={(e) => setFormData({...formData, name: e.target.value})}
                placeholder="John Doe"
              />
            </div>
            <div className="group">
              <label className="block text-xs sm:text-sm font-medium text-gray-300 mb-1.5 sm:mb-2" htmlFor="email">
                Email Address
              </label>
              <input
                id="email"
                type="email"
                required
                className="glass-input w-full px-3 py-2.5 sm:px-4 sm:py-3 rounded-lg sm:rounded-xl text-sm sm:text-base focus:ring-2 focus:ring-indigo-500/50"
                value={formData.email}
                onChange={(e) => setFormData({...formData, email: e.target.value})}
                placeholder="john@example.com"
              />
            </div>
          </div>
          
          <div className="group">
            <label className="block text-xs sm:text-sm font-medium text-gray-300 mb-1.5 sm:mb-2" htmlFor="message">
              Your Issue
            </label>
            <textarea
              id="message"
              required
              rows={4}
              className="glass-input w-full px-3 py-2.5 sm:px-4 sm:py-3 rounded-lg sm:rounded-xl resize-none text-sm sm:text-base focus:ring-2 focus:ring-indigo-500/50"
              value={formData.message}
              onChange={(e) => setFormData({...formData, message: e.target.value})}
              placeholder="Please describe your issue in detail so our Autonomous CRM can assist you efficiently..."
            ></textarea>
          </div>

          <button
            type="submit"
            disabled={status === 'sending'}
            className={`glass-button w-full py-3 sm:py-4 rounded-lg sm:rounded-xl font-semibold text-base sm:text-lg flex items-center justify-center space-x-2 transition-all ${status === 'sending' ? 'opacity-70 cursor-wait' : 'hover:shadow-indigo-500/30'} `}
          >
            {status === 'sending' && (
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            )}
            <span>{status === 'sending' ? 'Analyzing Request...' : 'Send Request'}</span>
            {!status && (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 ml-2" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            )}
          </button>

          {status === 'success' && (
            <div className="mt-4 p-3 sm:p-4 rounded-lg sm:rounded-xl bg-green-500/10 border border-green-500/30 text-green-400 text-sm sm:text-base text-center animate-pulse flex items-center justify-center">
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
              </svg>
              <span>Your request has been queued! Our Digital FTE is on it.</span>
            </div>
          )}
          {status === 'error' && (
            <div className="mt-4 p-3 sm:p-4 rounded-lg sm:rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm sm:text-base text-center flex items-center justify-center">
              <svg className="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd"></path>
              </svg>
              <span>Failed to connect to the intake service. Ensure local backend is running!</span>
            </div>
          )}
        </form>
      </div>

      <div className="mt-8 sm:mt-12 text-center text-xs sm:text-sm text-gray-500 z-10 relative mt-auto">
        <p>Autonomous Customer Success Portal • Powered by Gemini 2.5 Flash & Kafka</p>
      </div>
    </main>
  );
}
