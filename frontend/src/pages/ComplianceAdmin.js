import React, { useCallback, useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { ClipboardList } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

const STATUS_OPTIONS = ['open', 'in_progress', 'complete', 'waived'];
const FRAMEWORK_OPTIONS = ['irb', 'hipaa', 'gdpr'];

function mergeRow(row, edits) {
  return { ...row, ...(edits[row.id] || {}) };
}

const ComplianceAdmin = () => {
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [frameworkFilter, setFrameworkFilter] = useState('');
  const [edits, setEdits] = useState({});
  const [createForm, setCreateForm] = useState({
    framework: 'hipaa',
    control_code: '',
    title: '',
    tenant_id: '',
  });

  const load = useCallback(async () => {
    setListLoading(true);
    try {
      const params = frameworkFilter ? { framework: frameworkFilter } : {};
      const { data } = await api.admin.compliance.listChecklistItems(params);
      setItems(data.items || []);
    } catch (e) {
      toast.error('Could not load compliance checklist.');
    } finally {
      setListLoading(false);
    }
  }, [frameworkFilter]);

  useEffect(() => {
    if (authLoading || user?.role !== 'admin') return;
    load();
  }, [authLoading, user?.id, user?.role, load]);

  const patchField = (id, patch) => {
    setEdits((prev) => ({
      ...prev,
      [id]: { ...(prev[id] || {}), ...patch },
    }));
  };

  const saveRow = async (row) => {
    const m = mergeRow(row, edits);
    try {
      await api.admin.compliance.patchChecklistItem(row.id, {
        status: m.status,
        evidence_link: m.evidence_link ?? null,
        notes: m.notes ?? null,
      });
      toast.success('Checklist item saved.');
      setEdits((prev) => {
        const next = { ...prev };
        delete next[row.id];
        return next;
      });
      await load();
    } catch (err) {
      const d = err.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Save failed.');
    }
  };

  const createItem = async (e) => {
    e.preventDefault();
    if (!createForm.control_code.trim() || !createForm.title.trim()) {
      toast.error('Control code and title are required.');
      return;
    }
    try {
      const body = {
        framework: createForm.framework,
        control_code: createForm.control_code.trim(),
        title: createForm.title.trim(),
      };
      if (createForm.tenant_id.trim()) {
        body.tenant_id = createForm.tenant_id.trim();
      }
      await api.admin.compliance.createChecklistItem(body);
      toast.success('Checklist item created.');
      setCreateForm((f) => ({
        ...f,
        control_code: '',
        title: '',
        tenant_id: '',
      }));
      await load();
    } catch (err) {
      const d = err.response?.data?.detail;
      toast.error(typeof d === 'string' ? d : 'Create failed.');
    }
  };

  if (authLoading) {
    return (
      <div className="flex justify-center py-16 text-gray-600" role="status">
        Loading…
      </div>
    );
  }

  if (!user || user.role !== 'admin') {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start gap-4">
        <ClipboardList className="h-10 w-10 text-primary-600 shrink-0" aria-hidden />
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Compliance checklist (admin)</h1>
          <p className="mt-2 text-gray-600 max-w-3xl">
            Manage IRB, HIPAA, and GDPR control items. Status <code className="text-sm bg-gray-100 px-1 rounded">complete</code>{' '}
            requires a non-empty evidence link; <code className="text-sm bg-gray-100 px-1 rounded">waived</code> requires
            notes (at least 20 characters) documenting the waiver.
          </p>
        </div>
      </div>

      <section className="card p-6" aria-labelledby="create-heading">
        <h2 id="create-heading" className="text-lg font-semibold text-gray-900">
          New checklist item
        </h2>
        <form className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" onSubmit={createItem}>
          <label className="block text-sm text-gray-700">
            Framework
            <select
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
              value={createForm.framework}
              onChange={(e) => setCreateForm((f) => ({ ...f, framework: e.target.value }))}
            >
              {FRAMEWORK_OPTIONS.map((fw) => (
                <option key={fw} value={fw}>
                  {fw.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm text-gray-700">
            Control code
            <input
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
              value={createForm.control_code}
              onChange={(e) => setCreateForm((f) => ({ ...f, control_code: e.target.value }))}
              placeholder="e.g. 164.308(a)(1)"
            />
          </label>
          <label className="block text-sm text-gray-700 sm:col-span-2">
            Title
            <input
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
              value={createForm.title}
              onChange={(e) => setCreateForm((f) => ({ ...f, title: e.target.value }))}
            />
          </label>
          <label className="block text-sm text-gray-700 sm:col-span-2">
            Tenant ID (optional)
            <input
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
              value={createForm.tenant_id}
              onChange={(e) => setCreateForm((f) => ({ ...f, tenant_id: e.target.value }))}
              placeholder="Leave blank for global / unset"
            />
          </label>
          <div className="flex items-end">
            <button type="submit" className="btn-primary">
              Create
            </button>
          </div>
        </form>
      </section>

      <section className="card p-6" aria-labelledby="list-heading">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 id="list-heading" className="text-lg font-semibold text-gray-900">
            Items
          </h2>
          <label className="text-sm text-gray-700 flex items-center gap-2">
            Filter
            <select
              className="border border-gray-300 rounded-md p-2"
              value={frameworkFilter}
              onChange={(e) => setFrameworkFilter(e.target.value)}
            >
              <option value="">All</option>
              {FRAMEWORK_OPTIONS.map((fw) => (
                <option key={fw} value={fw}>
                  {fw.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4 overflow-x-auto">
          {listLoading ? (
            <p className="text-gray-600" role="status">
              Loading items…
            </p>
          ) : items.length === 0 ? (
            <p className="text-gray-600">No items match this filter.</p>
          ) : (
            <table className="min-w-full text-sm text-left border-collapse">
              <thead>
                <tr className="border-b border-gray-200 text-gray-600">
                  <th className="py-2 pr-4 font-medium">Framework</th>
                  <th className="py-2 pr-4 font-medium">Code</th>
                  <th className="py-2 pr-4 font-medium">Title</th>
                  <th className="py-2 pr-4 font-medium">Status</th>
                  <th className="py-2 pr-4 font-medium">Evidence link</th>
                  <th className="py-2 pr-4 font-medium">Notes</th>
                  <th className="py-2 pr-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const m = mergeRow(row, edits);
                  return (
                    <tr key={row.id} className="border-b border-gray-100 align-top">
                      <td className="py-2 pr-4 whitespace-nowrap">{m.framework}</td>
                      <td className="py-2 pr-4 font-mono text-xs">{m.control_code}</td>
                      <td className="py-2 pr-4 max-w-xs">{m.title}</td>
                      <td className="py-2 pr-4">
                        <select
                          className="border border-gray-300 rounded p-1 max-w-[9rem]"
                          aria-label={`Status for ${m.control_code}`}
                          value={m.status}
                          onChange={(e) => patchField(row.id, { status: e.target.value })}
                        >
                          {STATUS_OPTIONS.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-2 pr-4 min-w-[12rem]">
                        <input
                          className="w-full border border-gray-300 rounded p-1 text-xs"
                          aria-label={`Evidence link for ${m.control_code}`}
                          value={m.evidence_link || ''}
                          onChange={(e) => patchField(row.id, { evidence_link: e.target.value })}
                          placeholder="https://… or ticket"
                        />
                      </td>
                      <td className="py-2 pr-4 min-w-[14rem]">
                        <textarea
                          className="w-full border border-gray-300 rounded p-1 text-xs"
                          rows={2}
                          aria-label={`Notes for ${m.control_code}`}
                          value={m.notes || ''}
                          onChange={(e) => patchField(row.id, { notes: e.target.value })}
                        />
                      </td>
                      <td className="py-2 pr-4">
                        <button
                          type="button"
                          className="text-primary-700 hover:underline text-xs font-medium"
                          onClick={() => saveRow(row)}
                        >
                          Save
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
};

export default ComplianceAdmin;
