import { Routes, Route } from 'react-router-dom'
import { AppProvider } from './context/AppContext'

// Layouts
import { PublicLayout } from './layouts/PublicLayout'
import { StudentLayout } from './layouts/StudentLayout'
import { AdminLayout } from './layouts/AdminLayout'
import { StaffLayout } from './layouts/StaffLayout'
import { RequireRole } from './components/RequireRole'

// Public Pages
import { HomePage } from './pages/public/HomePage'
import { AboutPage } from './pages/public/AboutPage'
import { FacilitiesPage } from './pages/public/FacilitiesPage'
import { HostelLifePage } from './pages/public/HostelLifePage'
import { HowItWorksPage } from './pages/public/HowItWorksPage'
import { ContactPage } from './pages/public/ContactPage'
import { LoginPage } from './pages/public/LoginPage'
import { RegisterPage } from './pages/public/RegisterPage'
import { ForgotPasswordPage } from './pages/public/ForgotPasswordPage'
import { ResetPasswordPage } from './pages/public/ResetPasswordPage'

// Student Pages
import { StudentDashboardPage } from './pages/student/StudentDashboardPage'
import { StudentProfilePage } from './pages/student/StudentProfilePage'
import { StudentRoomPage } from './pages/student/StudentRoomPage'
import { StudentComplaintsPage } from './pages/student/StudentComplaintsPage'
import { SubmitComplaintPage } from './pages/student/SubmitComplaintPage'
import { ComplaintDetailPage } from './pages/student/ComplaintDetailPage'
import { StudentNotificationsPage } from './pages/student/StudentNotificationsPage'
import { StudentFinesPage } from './pages/student/fines/StudentFinesPage'
import { StudentFineDetailPage } from './pages/student/fines/StudentFineDetailPage'
import { StudentFineDisputePage } from './pages/student/fines/StudentFineDisputePage'
import { StudentFineHistoryPage } from './pages/student/fines/StudentFineHistoryPage'

// Admin Pages
import { AdminOverviewPage } from './pages/admin/AdminOverviewPage'
import { AdminStudentsPage } from './pages/admin/AdminStudentsPage'
import { RegistrationApprovalsPage } from './pages/admin/RegistrationApprovalsPage'
import { AdminRoomsPage } from './pages/admin/AdminRoomsPage'
import { AdminComplaintsPage } from './pages/admin/AdminComplaintsPage'
import { AdminComplaintDetailPage } from './pages/admin/AdminComplaintDetailPage'
import { AdminStaffPage } from './pages/admin/AdminStaffPage'
import { AdminAuditLogsPage } from './pages/admin/AdminAuditLogsPage'
import { AdminFinesPage } from './pages/admin/fines/AdminFinesPage'
import { AdminIssueFinePage } from './pages/admin/fines/AdminIssueFinePage'
import { AdminFineDetailPage } from './pages/admin/fines/AdminFineDetailPage'
import { AdminFineDisputesPage } from './pages/admin/fines/AdminFineDisputesPage'
import { AdminViolationsPage } from './pages/admin/fines/AdminViolationsPage'

// Staff Pages
import { StaffLoginPage } from './pages/staff/StaffLoginPage'
import { StaffDashboardPage } from './pages/staff/StaffDashboardPage'
import { StaffTasksPage } from './pages/staff/StaffTasksPage'
import { StaffTaskDetailPage } from './pages/staff/StaffTaskDetailPage'
import { StaffProfilePage } from './pages/staff/StaffProfilePage'
import { StaffNotificationsPage } from './pages/staff/StaffNotificationsPage'

// 404
import { NotFoundPage } from './pages/NotFoundPage'

export default function App() {
  return (
    <AppProvider>
      <Routes>
        {/* Public Website Routes */}
        <Route element={<PublicLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/facilities" element={<FacilitiesPage />} />
          <Route path="/hostel-life" element={<HostelLifePage />} />
          <Route path="/how-it-works" element={<HowItWorksPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/forgot-password" element={<ForgotPasswordPage />} />
          <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
          <Route path="/staff/login" element={<StaffLoginPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>

        {/* Student Portal Protected Routes */}
        <Route element={<RequireRole allowedRoles={['student']} />}>
          <Route element={<StudentLayout />}>
            <Route path="/student/dashboard" element={<StudentDashboardPage />} />
            <Route path="/student/profile" element={<StudentProfilePage />} />
            <Route path="/student/room" element={<StudentRoomPage />} />
            <Route path="/student/complaints" element={<StudentComplaintsPage />} />
            <Route path="/student/complaints/new" element={<SubmitComplaintPage />} />
            <Route path="/student/complaints/:id" element={<ComplaintDetailPage />} />
            <Route path="/student/fines" element={<StudentFinesPage />} />
            <Route path="/student/fines/:id" element={<StudentFineDetailPage />} />
            <Route path="/student/fines/:id/dispute" element={<StudentFineDisputePage />} />
            <Route path="/student/fines/history" element={<StudentFineHistoryPage />} />
            <Route path="/student/notifications" element={<StudentNotificationsPage />} />
          </Route>
        </Route>

        {/* Admin Portal Protected Routes */}
        <Route element={<RequireRole allowedRoles={['admin']} />}>
          <Route element={<AdminLayout />}>
            <Route path="/admin/dashboard" element={<AdminOverviewPage />} />
            <Route path="/admin/students" element={<AdminStudentsPage />} />
            <Route path="/admin/approvals" element={<RegistrationApprovalsPage />} />
            <Route path="/admin/rooms" element={<AdminRoomsPage />} />
            <Route path="/admin/complaints" element={<AdminComplaintsPage />} />
            <Route path="/admin/complaints/:id" element={<AdminComplaintDetailPage />} />
            <Route path="/admin/fines" element={<AdminFinesPage />} />
            <Route path="/admin/fines/new" element={<AdminIssueFinePage />} />
            <Route path="/admin/fines/:id" element={<AdminFineDetailPage />} />
            <Route path="/admin/fine-disputes" element={<AdminFineDisputesPage />} />
            <Route path="/admin/violations" element={<AdminViolationsPage />} />
            <Route path="/admin/staff" element={<AdminStaffPage />} />
            <Route path="/admin/audit-logs" element={<AdminAuditLogsPage />} />
          </Route>
        </Route>

        {/* Staff Portal Protected Routes */}
        <Route element={<RequireRole allowedRoles={['staff']} />}>
          <Route element={<StaffLayout />}>
            <Route path="/staff/dashboard" element={<StaffDashboardPage />} />
            <Route path="/staff/tasks" element={<StaffTasksPage />} />
            <Route path="/staff/tasks/:id" element={<StaffTaskDetailPage />} />
            <Route path="/staff/profile" element={<StaffProfilePage />} />
            <Route path="/staff/notifications" element={<StaffNotificationsPage />} />
          </Route>
        </Route>
      </Routes>
    </AppProvider>
  )
}
