import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Workspace from './Workspace';
import { publicApi } from './publicApi';

export default function PublicApp() {
  return <BrowserRouter><Routes>
    <Route path="/showcase/:projectId?/:view?" element={<Workspace client={publicApi} publicAccess />} />
    <Route path="*" element={<Navigate to="/showcase" replace />} />
  </Routes></BrowserRouter>;
}
