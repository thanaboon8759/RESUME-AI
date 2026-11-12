"""
Air-Gapped Web Testing Console for Resume AI Resume Intelligence Pipeline
Provides interactive single-document processing, batch directory scanning,
real-time telemetry, and structured CandidateProfile visualization.
Zero cloud APIs. 100% self-hosted on local RTX 4080 (16GB VRAM) via Ollama.
"""

# CRITICAL: torch must be imported before any library that loads PaddleOCR
import torch

import os
import sys
import time
import json
import shutil
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from schemas.models import RoutingResult, FileType, RouteDecision, CandidateProfile
from parsers.router import route_file, route_files
from parsers.docling_parser import parse_with_docling
from parsers.ocr_engine import extract_with_ocr
from optimized_pdf_engine import OptimizedPDFEngine
from extraction.llm_local import (
    extract_candidate_profile,
    extract_with_fallback,
    OllamaConnectionError,
    ExtractionError,
    check_ollama_connectivity,
)
from matching.bge_matcher import SkillMatcher

# Module-level singletons to prevent expensive re-instantiation per request
BENCHMARK_DATA_DIR = Path("benchmark_data")
pdf_engine = OptimizedPDFEngine(garble_threshold=0.15, ocr_dpi=150)
skill_matcher = SkillMatcher(model_name="BAAI/bge-m3", similarity_threshold=0.85)

app = FastAPI(title="Resume AI Web Testing Console")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class BatchRequest(BaseModel):
    directory: str = "benchmark_data"
    model: str = "qwen2.5:7b"
    mode: str = "auto"


HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Resume AI - Air-Gapped Resume Intelligence Console</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Air-gapped fallback styles in case CDN is offline */
    body { background-color: #0f172a; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .tab-active { border-bottom: 2px solid #3b82f6; color: #3b82f6; font-weight: 600; }
    pre { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  </style>
</head>
<body class="bg-slate-900 text-slate-100 min-h-screen antialiased flex flex-col">

  <!-- Header -->
  <header class="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center font-black text-sm tracking-wider shadow">AI</div>
        <div>
          <h1 class="text-base font-bold leading-tight tracking-wide">Resume AI</h1>
          <p class="text-xs text-slate-400">Air-Gapped Resume Intelligence &amp; Benchmark Console</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span id="gpuStatusBadge" class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          RTX 4080 (16GB) Local
        </span>
        <span id="ollamaStatusBadge" class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
          Ollama: Checking...
        </span>
      </div>
    </div>
  </header>

  <!-- Error Alert Banner -->
  <div id="errorBanner" class="hidden max-w-7xl mx-auto px-4 mt-4 w-full">
    <div class="bg-red-500/10 border border-red-500/30 text-red-300 text-xs px-4 py-3 rounded-xl flex items-center justify-between">
      <span id="errorMessage">Error message here</span>
      <button onclick="dismissError()" class="text-red-400 hover:text-white font-bold ml-4">Dismiss</button>
    </div>
  </div>

  <!-- Main Container -->
  <main class="max-w-7xl mx-auto px-4 py-6 flex-1 w-full grid grid-cols-1 lg:grid-cols-12 gap-6">

    <!-- Left Controls Panel (4 Cols) -->
    <div class="lg:col-span-4 space-y-5">

      <!-- Upload & Quick Samples Card -->
      <div class="bg-slate-800/90 border border-slate-700/80 rounded-xl p-5 shadow-lg space-y-4">
        <h2 class="text-xs font-bold text-slate-300 uppercase tracking-wider">1. Select Document</h2>
        
        <!-- File Dropzone -->
        <div id="dropzone" class="border-2 border-dashed border-slate-600 hover:border-blue-500 transition rounded-xl p-4 text-center cursor-pointer bg-slate-900/60">
          <input type="file" id="fileInput" class="hidden" accept=".pdf,.docx,.png,.jpg,.jpeg">
          <div class="text-xs text-slate-300 font-medium">Click or Drag &amp; Drop Resume</div>
          <div class="text-[11px] text-slate-500 mt-1">PDF, DOCX, PNG, JPG</div>
          <div id="selectedFileName" class="text-xs text-blue-400 font-semibold mt-2 hidden truncate"></div>
        </div>

        <!-- Quick Sample Buttons (All 7 Benchmark Files) -->
        <div>
          <div class="text-xs text-slate-400 mb-2 font-medium">Or Quick-Load Benchmark Sample:</div>
          <div class="grid grid-cols-2 gap-1.5" id="samplesContainer">
            <button onclick="loadSample('kunanon_resume.pdf')" id="btn-kunanon_resume.pdf" class="col-span-2 sample-btn px-2.5 py-1.5 text-xs bg-blue-900/40 hover:bg-blue-800/60 rounded-lg border border-blue-500/50 text-left transition truncate text-blue-300 font-semibold">
              Kunanon Hirunrattanaporn (Cybersecurity PDF)
            </button>
            <button onclick="loadSample('thai_resume.pdf')" id="btn-thai_resume.pdf" class="sample-btn px-2.5 py-1.5 text-xs bg-slate-900 hover:bg-slate-700 rounded-lg border border-slate-700 text-left transition truncate">
              Thai Resume (PDF)
            </button>
            <button onclick="loadSample('english_resume.pdf')" id="btn-english_resume.pdf" class="sample-btn px-2.5 py-1.5 text-xs bg-slate-900 hover:bg-slate-700 rounded-lg border border-slate-700 text-left transition truncate">
              English Resume (PDF)
            </button>
            <button onclick="loadSample('bilingual_resume.pdf')" id="btn-bilingual_resume.pdf" class="sample-btn px-2.5 py-1.5 text-xs bg-slate-900 hover:bg-slate-700 rounded-lg border border-slate-700 text-left transition truncate">
              Bilingual (PDF)
            </button>
            <button onclick="loadSample('scanned_resume.png')" id="btn-scanned_resume.png" class="sample-btn px-2.5 py-1.5 text-xs bg-slate-900 hover:bg-slate-700 rounded-lg border border-slate-700 text-left transition truncate">
              Scanned Image (PNG)
            </button>
            <button onclick="loadSample('real_functional_resume.pdf')" id="btn-real_functional_resume.pdf" class="col-span-2 sample-btn px-2.5 py-1.5 text-xs bg-slate-900 hover:bg-slate-700 rounded-lg border border-slate-700 text-left transition truncate">
              Real Functional Resume (PDF)
            </button>
          </div>
        </div>
      </div>

      <!-- Configuration Card -->
      <div class="bg-slate-800/90 border border-slate-700/80 rounded-xl p-5 shadow-lg space-y-4">
        <h2 class="text-xs font-bold text-slate-300 uppercase tracking-wider">2. Configuration</h2>
        
        <div>
          <label class="block text-xs font-medium text-slate-300 mb-1">Local LLM Extractor</label>
          <select id="modelSelect" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500">
            <option value="qwen2.5:7b" selected>qwen2.5:7b (Top Accuracy &amp; F1)</option>
            <option value="scb10x/typhoon2:8b">scb10x/typhoon2:8b (Thai Specialized)</option>
            <option value="llama3.1:8b">llama3.1:8b (Generalist)</option>
            <option value="deepseek-r1:8b">deepseek-r1:8b (Reasoning)</option>
          </select>
        </div>

        <div>
          <label class="block text-xs font-medium text-slate-300 mb-1">Routing Mode</label>
          <select id="modeSelect" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500">
            <option value="auto" selected>Auto Gateway (3-Signal Garble Detection)</option>
            <option value="vector_fastpath">Force Vector Fast-Path (&lt; 10ms)</option>
            <option value="ocr_engine">Force Typhoon OCR (Vision-Language)</option>
          </select>
        </div>

        <button id="runBtn" onclick="runSinglePipeline()" class="w-full py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-500 active:scale-[0.99] font-bold text-xs tracking-wider uppercase transition shadow-md flex items-center justify-center gap-2">
          Run Parsing &amp; Extraction
        </button>
      </div>

      <!-- Batch Directory Scan Card -->
      <div class="bg-slate-800/90 border border-slate-700/80 rounded-xl p-5 shadow-lg space-y-3">
        <h2 class="text-xs font-bold text-slate-300 uppercase tracking-wider">3. Batch Directory Scan</h2>
        <div>
          <label class="block text-xs text-slate-400 mb-1">Directory Path</label>
          <input type="text" id="batchDirInput" value="benchmark_data" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-indigo-500">
        </div>
        <button id="batchBtn" onclick="runBatchScan()" class="w-full py-2 px-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 active:scale-[0.99] font-bold text-xs tracking-wider uppercase transition shadow-md">
          Batch Scan Directory
        </button>
      </div>

      <!-- Live Telemetry Card -->
      <div id="telemetryCard" class="bg-slate-800/90 border border-slate-700/80 rounded-xl p-5 shadow-lg space-y-3 hidden">
        <h2 class="text-xs font-bold text-slate-300 uppercase tracking-wider">Live Telemetry &amp; Routing</h2>
        <div class="space-y-2 text-xs">
          <div class="flex justify-between py-1 border-b border-slate-700/50">
            <span class="text-slate-400">Selected Route:</span>
            <span id="routeBadge" class="font-bold text-emerald-400">Vector Fast-Path</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-700/50">
            <span class="text-slate-400">Thai Garble Score:</span>
            <span id="garbleScore" class="font-mono text-slate-200">0.034 (Clean)</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-700/50">
            <span class="text-slate-400">Total Latency:</span>
            <span id="totalLatency" class="font-bold text-blue-400">1,240 ms</span>
          </div>
          <div class="flex justify-between py-1 border-b border-slate-700/50">
            <span class="text-slate-400">Schema Validation:</span>
            <span id="schemaValid" class="font-bold text-emerald-400">PASSED (Pydantic v2)</span>
          </div>
          <div class="flex justify-between py-1">
            <span class="text-slate-400">Extraction Confidence:</span>
            <span id="confidenceScore" class="font-bold text-indigo-400">1.00</span>
          </div>
        </div>
      </div>

    </div>

    <!-- Right Results Panel (8 Cols) -->
    <div class="lg:col-span-8 space-y-5">

      <!-- Tabs Header -->
      <div class="border-b border-slate-800 flex items-center gap-6 text-sm overflow-x-auto">
        <button onclick="switchTab('profile')" id="tabBtn-profile" class="tab-active py-2 transition shrink-0">Candidate Profile</button>
        <button onclick="switchTab('skills')" id="tabBtn-skills" class="py-2 text-slate-400 hover:text-slate-200 transition shrink-0">Skills &amp; Normalization</button>
        <button onclick="switchTab('markdown')" id="tabBtn-markdown" class="py-2 text-slate-400 hover:text-slate-200 transition shrink-0">Parsed Markdown</button>
        <button onclick="switchTab('json')" id="tabBtn-json" class="py-2 text-slate-400 hover:text-slate-200 transition shrink-0">Raw JSON</button>
        <button onclick="switchTab('batch')" id="tabBtn-batch" class="py-2 text-slate-400 hover:text-slate-200 transition shrink-0 hidden">Batch Results (<span id="batchCountBadge">0</span>)</button>
      </div>

      <!-- State: Empty Placeholder -->
      <div id="emptyState" class="bg-slate-800/40 border border-dashed border-slate-700 rounded-2xl p-16 text-center space-y-3">
        <div class="text-slate-400 font-semibold text-sm">No Document Processed Yet</div>
        <p class="text-xs text-slate-500 max-w-sm mx-auto">Select a benchmark resume on the left or upload your own file, then click "Run Parsing &amp; Extraction".</p>
      </div>

      <!-- State: Loading Spinner -->
      <div id="loadingState" class="hidden bg-slate-800/40 border border-slate-700 rounded-2xl p-16 text-center space-y-4">
        <div class="inline-block w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <div class="text-sm font-semibold text-slate-200" id="loadingText">Processing document with local RTX 4080 engine...</div>
        <div class="text-xs text-slate-400" id="loadingSubtext">Routing, parsing, extracting schema, and normalizing skills</div>
      </div>

      <!-- Tab A: Candidate Profile -->
      <div id="tabContent-profile" class="hidden space-y-5">
        
        <!-- Header Info Card -->
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-md space-y-4">
          <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
            <div>
              <h2 id="profName" class="text-2xl font-bold text-white tracking-tight">Candidate Name</h2>
              <div id="profRole" class="text-sm font-semibold text-blue-400 mt-0.5">Current Role</div>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <span id="profSeniority" class="px-3 py-1 rounded-full text-xs font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Senior</span>
              <span id="profYears" class="px-3 py-1 rounded-full text-xs font-semibold bg-slate-700 text-slate-300 border border-slate-600">8.0 Years Exp</span>
            </div>
          </div>

          <div id="profContact" class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-slate-300 border-t border-slate-700/60 pt-3">
            <div><span class="text-slate-500 font-medium">Email:</span> <span id="profEmail">-</span></div>
            <div><span class="text-slate-500 font-medium">Phone:</span> <span id="profPhone">-</span></div>
          </div>

          <div id="profSummaryBox" class="bg-slate-900/70 border border-slate-700/50 rounded-lg p-3 text-xs text-slate-300 leading-relaxed">
            <span class="font-semibold text-slate-200">Executive Summary: </span>
            <span id="profSummary">-</span>
          </div>

          <!-- Languages & Implicit Skills -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <span class="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Languages</span>
              <div id="profLanguages" class="flex flex-wrap gap-1.5"></div>
            </div>
            <div>
              <span class="text-xs font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Implicit Skills Inferred</span>
              <div id="profImplicitSkills" class="flex flex-wrap gap-1.5"></div>
            </div>
          </div>
        </div>

        <!-- Work Experience Timeline -->
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-md space-y-4">
          <h3 class="text-xs font-bold uppercase tracking-wider text-slate-300">Professional Experience</h3>
          <div id="profExperienceList" class="space-y-4"></div>
        </div>

        <!-- Education Section -->
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-md space-y-4">
          <h3 class="text-xs font-bold uppercase tracking-wider text-slate-300">Education</h3>
          <div id="profEducationList" class="grid grid-cols-1 sm:grid-cols-2 gap-3"></div>
        </div>

      </div>

      <!-- Tab B: Skills & Normalization -->
      <div id="tabContent-skills" class="hidden bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-md space-y-5">
        <div>
          <div class="flex items-center justify-between mb-2">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-300">Canonical Normalized Skills (BGE-M3 Matching)</h3>
            <span id="skillsSummaryBar" class="text-xs font-semibold text-indigo-400">0 of 0 matched</span>
          </div>
          <p class="text-xs text-slate-400 mb-4">Raw extracted skills mapped into canonical taxonomy with cosine similarity score.</p>
          <div id="skillsTable" class="divide-y divide-slate-700 text-xs"></div>
        </div>
      </div>

      <!-- Tab C: Parsed Markdown -->
      <div id="tabContent-markdown" class="hidden bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-md space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-300">Extracted Markdown Document</h3>
            <span id="markdownStats" class="text-xs text-slate-400">0 characters, 0 words</span>
          </div>
          <button onclick="copyMarkdown()" class="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg text-slate-200 transition font-semibold">Copy Markdown</button>
        </div>
        <pre id="rawMarkdownContent" class="bg-slate-950 p-4 rounded-lg text-xs font-mono text-slate-300 overflow-x-auto whitespace-pre-wrap max-h-[550px]"></pre>
      </div>

      <!-- Tab D: Raw JSON -->
      <div id="tabContent-json" class="hidden bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-md space-y-3">
        <div class="flex items-center justify-between">
          <h3 class="text-xs font-bold uppercase tracking-wider text-slate-300">CandidateProfile JSON Schema Output</h3>
          <div class="flex gap-2">
            <button onclick="copyJson()" class="text-xs bg-slate-700 hover:bg-slate-600 px-3 py-1.5 rounded-lg text-slate-200 transition font-semibold">Copy JSON</button>
            <button onclick="downloadJson()" class="text-xs bg-blue-600 hover:bg-blue-500 px-3 py-1.5 rounded-lg text-white transition font-semibold">Download JSON</button>
          </div>
        </div>
        <pre id="rawJsonContent" class="bg-slate-950 p-4 rounded-lg text-xs font-mono text-emerald-400 overflow-x-auto whitespace-pre max-h-[550px]"></pre>
      </div>

      <!-- Tab E: Batch Results -->
      <div id="tabContent-batch" class="hidden space-y-5">
        
        <!-- Batch KPI Bar -->
        <div class="grid grid-cols-3 gap-4">
          <div class="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
            <div class="text-xs text-slate-400">Total Processed</div>
            <div id="batchKpiTotal" class="text-xl font-bold text-white mt-1">0</div>
          </div>
          <div class="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
            <div class="text-xs text-slate-400">Total Latency</div>
            <div id="batchKpiTime" class="text-xl font-bold text-blue-400 mt-1">0 ms</div>
          </div>
          <div class="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
            <div class="text-xs text-slate-400">Avg Latency / File</div>
            <div id="batchKpiAvg" class="text-xl font-bold text-emerald-400 mt-1">0 ms</div>
          </div>
        </div>

        <!-- Candidate Comparison Table -->
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-5 shadow-md space-y-4">
          <div class="flex items-center justify-between">
            <h3 class="text-xs font-bold uppercase tracking-wider text-slate-300">Candidates Comparison</h3>
            <button onclick="exportBatchJson()" class="text-xs bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 rounded-lg text-white font-semibold transition">
              Export All as JSON
            </button>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-xs text-left">
              <thead class="text-slate-400 border-b border-slate-700 uppercase tracking-wider">
                <tr>
                  <th class="py-2 px-3">Filename</th>
                  <th class="py-2 px-3">Candidate</th>
                  <th class="py-2 px-3">Seniority</th>
                  <th class="py-2 px-3">Skills</th>
                  <th class="py-2 px-3">Route</th>
                  <th class="py-2 px-3">Latency</th>
                  <th class="py-2 px-3">Schema</th>
                </tr>
              </thead>
              <tbody id="batchTableBody" class="divide-y divide-slate-700/60 font-mono"></tbody>
            </table>
          </div>
        </div>

      </div>

    </div>

  </main>

  <script>
    let activeTab = 'profile';
    let selectedSample = 'kunanon_resume.pdf';
    let currentUploadedFile = null;
    let latestSingleData = null;
    let latestBatchData = null;

    // Check backend health on load
    window.onload = async () => {
      loadSample('kunanon_resume.pdf');
      try {
        const res = await fetch('/api/health');
        if (res.ok) {
          const h = await res.json();
          document.getElementById('ollamaStatusBadge').textContent = 'Ollama: Connected (' + h.models_count + ' models)';
          document.getElementById('ollamaStatusBadge').className = 'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
        } else {
          showError('Ollama daemon check failed. Ensure Ollama is running at localhost:11434');
        }
      } catch (e) {
        showError('Unable to connect to web backend. Ensure py -3.12 web_ui.py is running.');
      }
    };

    function showError(msg) {
      document.getElementById('errorMessage').textContent = msg;
      document.getElementById('errorBanner').classList.remove('hidden');
    }

    function dismissError() {
      document.getElementById('errorBanner').classList.add('hidden');
    }

    // Dropzone setup
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const selectedFileName = document.getElementById('selectedFileName');

    dropzone.onclick = () => fileInput.click();
    fileInput.onchange = (e) => {
      if (e.target.files.length > 0) {
        currentUploadedFile = e.target.files[0];
        selectedSample = null;
        selectedFileName.textContent = currentUploadedFile.name;
        selectedFileName.classList.remove('hidden');
        resetSampleHighlights();
      }
    };

    dropzone.ondragover = (e) => { e.preventDefault(); dropzone.classList.add('border-blue-500'); };
    dropzone.ondragleave = () => { dropzone.classList.remove('border-blue-500'); };
    dropzone.ondrop = (e) => {
      e.preventDefault();
      dropzone.classList.remove('border-blue-500');
      if (e.dataTransfer.files.length > 0) {
        currentUploadedFile = e.dataTransfer.files[0];
        selectedSample = null;
        selectedFileName.textContent = currentUploadedFile.name;
        selectedFileName.classList.remove('hidden');
        resetSampleHighlights();
      }
    };

    function resetSampleHighlights() {
      document.querySelectorAll('.sample-btn').forEach(b => {
        b.classList.remove('bg-blue-600/30', 'border-blue-500');
        b.classList.add('bg-slate-900', 'border-slate-700');
      });
    }

    function loadSample(sampleName) {
      selectedSample = sampleName;
      currentUploadedFile = null;
      selectedFileName.classList.add('hidden');
      resetSampleHighlights();
      const btn = document.getElementById('btn-' + sampleName);
      if (btn) {
        btn.classList.add('bg-blue-600/30', 'border-blue-500');
        btn.classList.remove('bg-slate-900', 'border-slate-700');
      }
    }

    function switchTab(tab) {
      activeTab = tab;
      ['profile', 'skills', 'markdown', 'json', 'batch'].forEach(t => {
        const btn = document.getElementById('tabBtn-' + t);
        const content = document.getElementById('tabContent-' + t);
        if (t === tab) {
          btn.className = "tab-active py-2 transition shrink-0";
          content.classList.remove('hidden');
        } else {
          btn.className = "py-2 text-slate-400 hover:text-slate-200 transition shrink-0";
          content.classList.add('hidden');
        }
      });
    }

    async function runSinglePipeline() {
      dismissError();
      const runBtn = document.getElementById('runBtn');
      const emptyState = document.getElementById('emptyState');
      const loadingState = document.getElementById('loadingState');
      const model = document.getElementById('modelSelect').value;
      const mode = document.getElementById('modeSelect').value;

      emptyState.classList.add('hidden');
      ['profile', 'skills', 'markdown', 'json'].forEach(t => document.getElementById('tabContent-' + t).classList.add('hidden'));
      loadingState.classList.remove('hidden');
      document.getElementById('loadingText').textContent = 'Processing document with local RTX 4080 engine...';
      document.getElementById('loadingSubtext').textContent = 'Routing, parsing text, LLM extraction, and skill normalization';
      runBtn.disabled = true;

      const formData = new FormData();
      formData.append('model', model);
      formData.append('mode', mode);
      if (currentUploadedFile) {
        formData.append('file', currentUploadedFile);
      } else {
        formData.append('sample', selectedSample);
      }

      try {
        const res = await fetch('/api/process', { method: 'POST', body: formData });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Processing failed');
        }
        const data = await res.json();
        latestSingleData = data;
        renderSingleResults(data);
      } catch (err) {
        showError(err.message);
        emptyState.classList.remove('hidden');
      } finally {
        loadingState.classList.add('hidden');
        runBtn.disabled = false;
      }
    }

    function renderSingleResults(data) {
      // Live Telemetry Card
      const telemetryCard = document.getElementById('telemetryCard');
      telemetryCard.classList.remove('hidden');
      document.getElementById('routeBadge').textContent = data.route;
      const isClean = data.garble_score < 0.15;
      document.getElementById('garbleScore').textContent = data.garble_score.toFixed(3) + (isClean ? ' (Clean)' : ' (Degraded / Garbled)');
      document.getElementById('garbleScore').className = 'font-mono ' + (isClean ? 'text-emerald-400' : 'text-amber-400');
      document.getElementById('totalLatency').textContent = data.total_latency_ms + ' ms';
      document.getElementById('schemaValid').textContent = data.schema_valid ? 'PASSED (Pydantic v2)' : 'FAILED';
      document.getElementById('confidenceScore').textContent = (data.profile.extraction_confidence || 1.0).toFixed(2);

      const p = data.profile;

      // Tab A: Profile
      document.getElementById('profName').textContent = p.full_name || 'N/A';
      document.getElementById('profRole').textContent = (p.experience && p.experience[0]) ? p.experience[0].role : 'Candidate';
      
      const senLevel = p.seniority_level || 'Mid-Level';
      document.getElementById('profSeniority').textContent = senLevel;
      const senColors = {
        'Junior': 'bg-slate-700 text-slate-300 border-slate-600',
        'Mid-Level': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
        'Senior': 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
        'Lead/Principal': 'bg-purple-500/20 text-purple-300 border-purple-500/30',
        'Executive': 'bg-amber-500/20 text-amber-300 border-amber-500/30'
      };
      document.getElementById('profSeniority').className = 'px-3 py-1 rounded-full text-xs font-semibold border ' + (senColors[senLevel] || senColors['Mid-Level']);
      document.getElementById('profYears').textContent = (p.total_years_experience || 0) + ' Years Exp';
      document.getElementById('profEmail').textContent = p.contact_email || 'Not Specified';
      document.getElementById('profPhone').textContent = p.contact_phone || 'Not Specified';
      document.getElementById('profSummary').textContent = p.executive_summary || 'No summary generated.';

      // Languages
      const langBox = document.getElementById('profLanguages');
      langBox.innerHTML = '';
      if (p.languages && p.languages.length > 0) {
        p.languages.forEach(l => {
          const pill = document.createElement('span');
          pill.className = "px-2 py-0.5 rounded bg-slate-700 text-slate-300 text-[11px] font-medium";
          pill.textContent = l;
          langBox.appendChild(pill);
        });
      } else {
        langBox.innerHTML = '<span class="text-slate-500 text-xs">None listed</span>';
      }

      // Implicit Skills
      const impBox = document.getElementById('profImplicitSkills');
      impBox.innerHTML = '';
      if (p.implicit_skills && p.implicit_skills.length > 0) {
        p.implicit_skills.forEach(s => {
          const pill = document.createElement('span');
          pill.className = "px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 text-[11px] font-medium border border-purple-500/30";
          pill.textContent = s;
          impBox.appendChild(pill);
        });
      } else {
        impBox.innerHTML = '<span class="text-slate-500 text-xs">None inferred</span>';
      }

      // Experience Timeline
      const expList = document.getElementById('profExperienceList');
      expList.innerHTML = '';
      if (p.experience && p.experience.length > 0) {
        p.experience.forEach(exp => {
          const card = document.createElement('div');
          card.className = "border-l-2 border-blue-500 pl-4 space-y-1";
          const dates = (exp.start_date || '') + ' - ' + (exp.end_date || 'Present');
          let bullets = '';
          if (exp.achievements) {
            bullets = exp.achievements.map(a => '<li>* ' + a + '</li>').join('');
          }
          card.innerHTML = `
            <div class="flex items-center justify-between text-xs">
              <span class="font-bold text-slate-100">${exp.role}</span>
              <span class="text-slate-400 font-mono">${dates}</span>
            </div>
            <div class="text-xs text-blue-400 font-semibold">${exp.company}</div>
            <ul class="text-xs text-slate-300 mt-1 space-y-0.5 list-none">${bullets}</ul>
          `;
          expList.appendChild(card);
        });
      } else {
        expList.innerHTML = '<div class="text-xs text-slate-500">No experience records detected.</div>';
      }

      // Education Cards
      const eduList = document.getElementById('profEducationList');
      eduList.innerHTML = '';
      if (p.education && p.education.length > 0) {
        p.education.forEach(edu => {
          const card = document.createElement('div');
          card.className = "bg-slate-900/60 p-3 rounded-lg border border-slate-700/40 text-xs";
          card.innerHTML = `
            <div class="font-bold text-slate-200">${edu.degree || 'Degree'}</div>
            <div class="text-slate-400 mt-0.5">${edu.institution || 'University'}</div>
            <div class="text-slate-500 text-[11px] mt-1">${edu.field_of_study || ''} ${edu.graduation_year ? '(' + edu.graduation_year + ')' : ''}</div>
          `;
          eduList.appendChild(card);
        });
      } else {
        eduList.innerHTML = '<div class="text-xs text-slate-500">No education records detected.</div>';
      }

      // Tab B: Skills & Normalization
      const skTable = document.getElementById('skillsTable');
      skTable.innerHTML = '';
      let matchedCount = 0;
      if (data.normalized_skills && data.normalized_skills.length > 0) {
        data.normalized_skills.forEach(item => {
          const isMatched = item.matched_canonical !== null;
          if (isMatched) matchedCount++;
          const row = document.createElement('div');
          row.className = "py-2 flex items-center justify-between";
          row.innerHTML = `
            <div>
              <span class="font-medium text-slate-200">${item.original}</span>
              <span class="text-slate-500 text-[11px] ml-2">&rarr;</span>
              <span class="ml-2 font-semibold ${isMatched ? 'text-indigo-400' : 'text-slate-500'}">
                ${item.matched_canonical || 'Unmapped Skill'}
              </span>
            </div>
            <div class="font-mono text-xs ${item.similarity_score >= 0.85 ? 'text-emerald-400 font-bold' : 'text-slate-500'}">
              Score: ${item.similarity_score.toFixed(2)}
            </div>
          `;
          skTable.appendChild(row);
        });
      }
      document.getElementById('skillsSummaryBar').textContent = matchedCount + ' of ' + (data.normalized_skills ? data.normalized_skills.length : 0) + ' skills matched to taxonomy';

      // Tab C: Markdown
      const md = data.markdown || '';
      document.getElementById('rawMarkdownContent').textContent = md;
      const wordCount = md.trim() ? md.trim().split(/\\s+/).length : 0;
      document.getElementById('markdownStats').textContent = md.length + ' characters, ' + wordCount + ' words';

      // Tab D: JSON
      document.getElementById('rawJsonContent').textContent = JSON.stringify(p, null, 2);

      switchTab('profile');
    }

    async function runBatchScan() {
      dismissError();
      const batchBtn = document.getElementById('batchBtn');
      const emptyState = document.getElementById('emptyState');
      const loadingState = document.getElementById('loadingState');
      const dirPath = document.getElementById('batchDirInput').value.trim();
      const model = document.getElementById('modelSelect').value;
      const mode = document.getElementById('modeSelect').value;

      emptyState.classList.add('hidden');
      ['profile', 'skills', 'markdown', 'json'].forEach(t => document.getElementById('tabContent-' + t).classList.add('hidden'));
      loadingState.classList.remove('hidden');
      document.getElementById('loadingText').textContent = 'Executing Batch Directory Scan on ' + dirPath + '...';
      document.getElementById('loadingSubtext').textContent = 'Sequential processing across all discovered documents to prevent GPU contention';
      batchBtn.disabled = true;

      try {
        const res = await fetch('/api/batch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ directory: dirPath, model: model, mode: mode })
        });
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || 'Batch scan failed');
        }
        const data = await res.json();
        latestBatchData = data;
        renderBatchResults(data);
      } catch (err) {
        showError(err.message);
        emptyState.classList.remove('hidden');
      } finally {
        loadingState.classList.add('hidden');
        batchBtn.disabled = false;
      }
    }

    function renderBatchResults(data) {
      document.getElementById('tabBtn-batch').classList.remove('hidden');
      document.getElementById('batchCountBadge').textContent = data.total_files;
      document.getElementById('batchKpiTotal').textContent = data.total_files;
      document.getElementById('batchKpiTime').textContent = data.total_latency_ms + ' ms';
      const avgMs = data.total_files > 0 ? Math.round(data.total_latency_ms / data.total_files) : 0;
      document.getElementById('batchKpiAvg').textContent = avgMs + ' ms';

      const tbody = document.getElementById('batchTableBody');
      tbody.innerHTML = '';

      data.results.forEach((r, idx) => {
        const tr = document.createElement('tr');
        tr.className = "hover:bg-slate-700/40 cursor-pointer transition";
        const p = r.profile || {};
        const skillsCount = (p.skills || []).length;
        tr.innerHTML = `
          <td class="py-2.5 px-3 text-slate-300 font-semibold truncate max-w-[140px]">${r.filename}</td>
          <td class="py-2.5 px-3 text-white">${p.full_name || 'N/A'}</td>
          <td class="py-2.5 px-3 text-indigo-300">${p.seniority_level || 'Mid-Level'}</td>
          <td class="py-2.5 px-3 text-slate-300">${skillsCount}</td>
          <td class="py-2.5 px-3 text-emerald-400">${r.route}</td>
          <td class="py-2.5 px-3 text-blue-400">${r.total_latency_ms} ms</td>
          <td class="py-2.5 px-3 ${r.schema_valid ? 'text-emerald-400' : 'text-red-400'}">${r.schema_valid ? 'VALID' : 'FAILED'}</td>
        `;
        tr.onclick = () => {
          latestSingleData = r;
          renderSingleResults(r);
        };
        tbody.appendChild(tr);
      });

      switchTab('batch');
    }

    function copyMarkdown() {
      if (latestSingleData && latestSingleData.markdown) {
        navigator.clipboard.writeText(latestSingleData.markdown);
        alert('Copied Markdown to clipboard');
      }
    }

    function copyJson() {
      if (latestSingleData && latestSingleData.profile) {
        navigator.clipboard.writeText(JSON.stringify(latestSingleData.profile, null, 2));
        alert('Copied JSON to clipboard');
      }
    }

    function downloadJson() {
      if (latestSingleData && latestSingleData.profile) {
        const blob = new Blob([JSON.stringify(latestSingleData.profile, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = (latestSingleData.filename || 'resume') + '_profile.json';
        a.click();
        URL.revokeObjectURL(url);
      }
    }

    function exportBatchJson() {
      if (latestBatchData && latestBatchData.results) {
        const blob = new Blob([JSON.stringify(latestBatchData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'batch_resume_profiles.json';
        a.click();
        URL.revokeObjectURL(url);
      }
    }
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def get_index():
    return HTMLResponse(content=HTML_CONTENT)


@app.get("/api/health")
def get_health():
    """Health check verifying GPU detection and local Ollama connectivity."""
    is_connected = check_ollama_connectivity(timeout=3.0)
    models_count = 0
    if is_connected:
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models_count = len(data.get("models", []))
        except Exception:
            pass

    return {
        "status": "healthy" if is_connected else "degraded",
        "ollama_connected": is_connected,
        "models_count": models_count,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None",
    }


@app.get("/api/samples")
def list_samples():
    """List all available benchmark sample files with sizes and types."""
    if not BENCHMARK_DATA_DIR.exists():
        return {"samples": []}

    samples = []
    for p in sorted(BENCHMARK_DATA_DIR.iterdir()):
        if p.is_file() and p.suffix.lower() in [".pdf", ".docx", ".png", ".jpg", ".jpeg"]:
            samples.append({
                "filename": p.name,
                "size_kb": round(p.stat().st_size / 1024, 1),
                "extension": p.suffix.lower().lstrip("."),
            })
    return {"samples": samples}


@app.get("/api/models")
def list_models():
    """Query local Ollama instance for installed models."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return {"models": data.get("models", [])}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama is not running at localhost:11434: {e}"
        )


def _execute_pipeline_on_file(
    target_path: Path,
    model: str = "qwen2.5:7b",
    mode: str = "auto"
) -> Dict[str, Any]:
    """Execute the full 4-stage pipeline sequentially on a single file."""
    t_start = time.perf_counter()

    # 1. Routing Gateway
    route_decision = route_file(target_path)
    garble = route_decision.garble_score

    # Mode override
    if mode == "vector_fastpath":
        use_ocr = False
        route_str = "Forced Vector Fast-Path (PyMuPDF)"
    elif mode == "ocr_engine":
        use_ocr = True
        route_str = "Forced OCR Engine (Typhoon VLM)"
    else:
        use_ocr = route_decision.requires_ocr
        route_str = "OCR Engine (Typhoon VLM)" if use_ocr else "Vector Fast-Path (Docling)"

    # 2. Parsing (Vector or OCR)
    if use_ocr:
        markdown_text = extract_with_ocr(str(target_path))
    else:
        if target_path.suffix.lower() == ".pdf":
            fast_res = pdf_engine.process_document(target_path)
            markdown_text = fast_res.get("text") or parse_with_docling(str(target_path))
        else:
            markdown_text = parse_with_docling(str(target_path))

    # 3. LLM Extraction
    try:
        profile = extract_candidate_profile(markdown_text, model=model)
        schema_valid = True
    except OllamaConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running at localhost:11434. Start with: ollama serve"
        )
    except Exception as e:
        # Fallback profile on extraction failure
        profile = CandidateProfile(
            full_name=target_path.stem.replace("_", " ").title(),
            executive_summary=f"Extraction failure: {e}",
            extraction_confidence=0.0
        )
        schema_valid = False

    # 4. Skill Normalization
    normalized = skill_matcher.normalize_skills(profile.skills)

    total_latency_ms = round((time.perf_counter() - t_start) * 1000)

    return {
        "filename": target_path.name,
        "route": route_str,
        "requires_ocr": use_ocr,
        "garble_score": garble,
        "total_latency_ms": total_latency_ms,
        "schema_valid": schema_valid,
        "markdown": markdown_text,
        "profile": profile.model_dump(),
        "normalized_skills": normalized
    }


@app.post("/api/process")
async def process_single_document(
    file: Optional[UploadFile] = File(None),
    sample: Optional[str] = Form(None),
    model: str = Form("qwen2.5:7b"),
    mode: str = Form("auto")
):
    temp_dir = tempfile.mkdtemp()
    target_path = None

    try:
        if file is not None and file.filename:
            target_path = Path(temp_dir) / file.filename
            with open(target_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        elif sample:
            sample_path = BENCHMARK_DATA_DIR / sample
            if not sample_path.exists():
                raise HTTPException(status_code=404, detail=f"Sample '{sample}' not found in benchmark_data")
            target_path = sample_path
        else:
            raise HTTPException(status_code=400, detail="No file or sample specified")

        result = _execute_pipeline_on_file(target_path, model=model, mode=mode)
        return JSONResponse(content=result)

    finally:
        if file is not None and Path(temp_dir).exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/api/batch")
def process_batch_directory(req: BatchRequest = Body(...)):
    target_dir = Path(req.directory)
    if not target_dir.exists() or not target_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory '{req.directory}' not found")

    supported_exts = {".pdf", ".docx", ".png", ".jpg", ".jpeg"}
    all_files = [p for p in sorted(target_dir.iterdir()) if p.is_file() and p.suffix.lower() in supported_exts]

    if not all_files:
        raise HTTPException(status_code=400, detail=f"No supported documents found in '{req.directory}'")

    t_batch_start = time.perf_counter()
    results = []

    # Process files sequentially to avoid GPU contention
    for file_path in all_files:
        try:
            res = _execute_pipeline_on_file(file_path, model=req.model, mode=req.mode)
            results.append(res)
        except Exception as e:
            results.append({
                "filename": file_path.name,
                "route": "Error",
                "requires_ocr": False,
                "garble_score": 0.0,
                "total_latency_ms": 0,
                "schema_valid": False,
                "markdown": f"Processing error: {e}",
                "profile": CandidateProfile(
                    full_name=file_path.stem,
                    executive_summary=f"Failed to process: {e}",
                    extraction_confidence=0.0
                ).model_dump(),
                "normalized_skills": []
            })

    total_batch_ms = round((time.perf_counter() - t_batch_start) * 1000)

    return JSONResponse(content={
        "total_files": len(results),
        "total_latency_ms": total_batch_ms,
        "results": results
    })


if __name__ == "__main__":
    print("[INFO] Starting Resume AI Web Testing Console on http://localhost:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)
