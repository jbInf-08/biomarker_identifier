import React from 'react';
import { Link } from 'react-router-dom';
import { FlaskConical } from 'lucide-react';

const Models = () => (
  <div className="space-y-6">
    <div>
      <h1 className="text-3xl font-bold text-gray-900">ML Models</h1>
      <p className="mt-2 text-gray-600">
        Train and manage machine learning models for biomarker analysis.
      </p>
    </div>
    <div className="card">
      <div className="text-center py-12">
        <FlaskConical className="h-16 w-16 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Model Training</h3>
        <p className="text-gray-500 mb-6">
          Train models from your completed biomarker analyses. Select a run with results to get started.
        </p>
        <Link to="/results" className="btn-primary">
          View Results
        </Link>
      </div>
    </div>
  </div>
);

export default Models;
