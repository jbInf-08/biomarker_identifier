import { clsx } from 'clsx';

export {
  shouldRunInit,
  markInitialized,
  markDestroyed,
  reviveLifecycle,
  LifecycleCapable,
} from './managedLifecycle';

export function cn(...inputs) {
  return clsx(inputs);
}

export function formatNumber(num, decimals = 2) {
  if (num === null || num === undefined) return 'N/A';
  return Number(num).toFixed(decimals);
}

export function formatPValue(pValue) {
  if (pValue === null || pValue === undefined) return 'N/A';
  if (pValue < 0.001) return '< 0.001';
  return pValue.toFixed(3);
}

export function formatDate(date) {
  if (!date) return 'N/A';
  return new Date(date).toLocaleDateString();
}

export function formatDateTime(date) {
  if (!date) return 'N/A';
  return new Date(date).toLocaleString();
}

export function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

export function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

export function throttle(func, limit) {
  let inThrottle;
  return function() {
    const args = arguments;
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

export function generateId() {
  return Math.random().toString(36).substr(2, 9);
}

export function downloadFile(data, filename, type = 'text/plain') {
  const blob = new Blob([data], { type });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

export function exportToCSV(data, filename) {
  if (!data || data.length === 0) return;
  
  const headers = Object.keys(data[0]);
  const csvContent = [
    headers.join(','),
    ...data.map(row => headers.map(header => `"${row[header] || ''}"`).join(','))
  ].join('\n');
  
  downloadFile(csvContent, filename, 'text/csv');
}

export function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return re.test(email);
}

export function validateFileType(file, allowedTypes) {
  return allowedTypes.includes(file.type);
}

export function validateFileSize(file, maxSizeMB) {
  const maxSizeBytes = maxSizeMB * 1024 * 1024;
  return file.size <= maxSizeBytes;
}

export function getFileExtension(filename) {
  return filename.split('.').pop().toLowerCase();
}

export function parseCSV(content) {
  const lines = content.split('\n');
  const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
  const data = lines.slice(1).map(line => {
    const values = line.split(',').map(v => v.trim().replace(/"/g, ''));
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] || '';
    });
    return row;
  });
  return { headers, data };
}

export function parseTSV(content) {
  const lines = content.split('\n');
  const headers = lines[0].split('\t').map(h => h.trim());
  const data = lines.slice(1).map(line => {
    const values = line.split('\t').map(v => v.trim());
    const row = {};
    headers.forEach((header, index) => {
      row[header] = values[index] || '';
    });
    return row;
  });
  return { headers, data };
}

export function getStatusColor(status) {
  switch (status?.toLowerCase()) {
    case 'completed':
    case 'success':
      return 'text-green-600 bg-green-100';
    case 'running':
    case 'processing':
      return 'text-blue-600 bg-blue-100';
    case 'failed':
    case 'error':
      return 'text-red-600 bg-red-100';
    case 'pending':
    case 'waiting':
      return 'text-yellow-600 bg-yellow-100';
    default:
      return 'text-gray-600 bg-gray-100';
  }
}

export function getStatusIcon(status) {
  switch (status?.toLowerCase()) {
    case 'completed':
    case 'success':
      return '✓';
    case 'running':
    case 'processing':
      return '⏳';
    case 'failed':
    case 'error':
      return '✗';
    case 'pending':
    case 'waiting':
      return '⏸';
    default:
      return '?';
  }
}
