import React from 'react';
import { Settings as SettingsIcon } from 'lucide-react';

const Settings = () => (
  <div className="space-y-6">
    <div>
      <h1 className="text-3xl font-bold text-gray-900">Settings</h1>
      <p className="mt-2 text-gray-600">
        Configure your application preferences.
      </p>
    </div>
    <div className="card">
      <div className="text-center py-12">
        <SettingsIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-gray-900 mb-2">Settings coming soon</h3>
        <p className="text-gray-500">
          Application settings will be available in a future release.
        </p>
      </div>
    </div>
  </div>
);

export default Settings;
