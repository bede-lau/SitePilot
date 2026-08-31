import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ComponentsPage from "./pages/Components";
import Dashboard from "./pages/Dashboard";
import Feasibility from "./pages/Feasibility";
import Procurement from "./pages/Procurement";
import ProjectDetail from "./pages/ProjectDetail";
import ProjectsList from "./pages/ProjectsList";
import PurchaseOrdersList from "./pages/PurchaseOrdersList";
import Vendors from "./pages/Vendors";

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/feasibility" element={<Feasibility />} />
        <Route path="/procurement" element={<Procurement />} />
        <Route path="/components" element={<ComponentsPage />} />
        <Route path="/projects" element={<ProjectsList />} />
        <Route path="/projects/:id" element={<ProjectDetail />} />
        <Route path="/vendors" element={<Vendors />} />
        <Route path="/purchase-orders" element={<PurchaseOrdersList />} />
      </Route>
    </Routes>
  );
}

export default App;
