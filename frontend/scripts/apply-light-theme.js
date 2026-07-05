#!/usr/bin/env node
/**
 * Adds light-mode base classes alongside existing dark slate utilities.
 * Skips tokens that already include "dark:".
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');

const REPLACEMENTS = [
  ['bg-slate-950/95', 'bg-white/95 dark:bg-slate-950/95'],
  ['bg-slate-900/95', 'bg-white/95 dark:bg-slate-900/95'],
  ['bg-slate-900/60', 'bg-slate-100/80 dark:bg-slate-900/60'],
  ['bg-slate-900/50', 'bg-white dark:bg-slate-900/50'],
  ['bg-slate-900/40', 'bg-slate-50 dark:bg-slate-900/40'],
  ['bg-slate-950/40', 'bg-slate-50 dark:bg-slate-950/40'],
  ['bg-slate-950/30', 'bg-slate-50 dark:bg-slate-950/30'],
  ['bg-slate-950/20', 'bg-slate-50 dark:bg-slate-950/20'],
  ['bg-slate-900/30', 'bg-slate-50 dark:bg-slate-900/30'],
  ['bg-slate-800/80', 'bg-slate-200/80 dark:bg-slate-800/80'],
  ['bg-slate-800/50', 'bg-slate-100 dark:bg-slate-800/50'],
  ['hover:bg-slate-900', 'hover:bg-slate-100 dark:hover:bg-slate-900'],
  ['hover:bg-slate-800', 'hover:bg-slate-100 dark:hover:bg-slate-800'],
  ['hover:bg-slate-700', 'hover:bg-slate-200 dark:hover:bg-slate-700'],
  ['hover:text-slate-200', 'hover:text-slate-900 dark:hover:text-slate-200'],
  ['hover:text-slate-100', 'hover:text-slate-900 dark:hover:text-slate-100'],
  ['hover:border-slate-600', 'hover:border-slate-400 dark:hover:border-slate-600'],
  ['placeholder-slate-600', 'placeholder-slate-400 dark:placeholder-slate-600'],
  ['placeholder-slate-500', 'placeholder-slate-400 dark:placeholder-slate-500'],
  ['border-slate-800', 'border-slate-200 dark:border-slate-800'],
  ['border-slate-700', 'border-slate-300 dark:border-slate-700'],
  ['border-slate-600', 'border-slate-300 dark:border-slate-600'],
  ['bg-slate-950', 'bg-white dark:bg-slate-950'],
  ['bg-slate-900', 'bg-slate-100 dark:bg-slate-900'],
  ['bg-slate-800', 'bg-slate-100 dark:bg-slate-800'],
  ['text-slate-50', 'text-slate-900 dark:text-slate-50'],
  ['text-slate-100', 'text-slate-900 dark:text-slate-100'],
  ['text-slate-200', 'text-slate-800 dark:text-slate-200'],
  ['text-slate-300', 'text-slate-700 dark:text-slate-300'],
  ['text-slate-400', 'text-slate-600 dark:text-slate-400'],
  ['text-slate-600', 'text-slate-500 dark:text-slate-600'],
];

const SKIP_FILES = new Set([
  'ThemeProvider.tsx',
  'ThemeToggle.tsx',
  'Sidebar.tsx',
  'AppShell.tsx',
  'BottomTaskbar.tsx',
  'layout.tsx',
  'globals.css',
  'tailwind.config.ts',
  'theme.ts',
]);

const SKIP_DIRS = new Set(['node_modules', '.next', 'out', 'scripts']);

function shouldSkip(filePath) {
  const base = path.basename(filePath);
  if (SKIP_FILES.has(base)) return true;
  const parts = filePath.split(path.sep);
  if (parts.some((p) => SKIP_DIRS.has(p))) return true;
  return false;
}

function walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, files);
    else if (/\.(tsx|ts|jsx|js)$/.test(entry.name)) files.push(full);
  }
  return files;
}

function applyReplacements(content) {
  let result = content;
  for (const [from, to] of REPLACEMENTS) {
    const escaped = from.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(?<!dark:)(?<![\\w-])${escaped}(?![0-9])`, 'g');
    result = result.replace(regex, to);
  }
  return result;
}

const files = walk(ROOT).filter((f) => !shouldSkip(f));
let changed = 0;

for (const file of files) {
  const before = fs.readFileSync(file, 'utf8');
  const after = applyReplacements(before);
  if (after !== before) {
    fs.writeFileSync(file, after);
    changed++;
    console.log('updated:', path.relative(ROOT, file));
  }
}

console.log(`Done. ${changed} file(s) updated.`);
