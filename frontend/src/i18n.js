import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
  en: {
    translation: {
      appName: 'Cancer Biomarker Identifier',
      nav: {
        dashboard: 'Dashboard',
        upload: 'Data Upload',
        monitoring: 'Pipeline Monitoring',
        results: 'Results',
        reports: 'Reports',
        clinical: 'Clinical Databases',
        models: 'ML Models',
        settings: 'Settings',
        complianceAdmin: 'Compliance (admin)',
        toolsResources: 'Tools & Resources',
      },
      header: {
        openMenu: 'Open menu',
        userMenu: 'User menu',
        profile: 'Profile',
        signOut: 'Sign out',
        notifications: 'Notifications',
        language: 'Language',
      },
      dashboard: {
        title: 'Dashboard',
        subtitle:
          'Welcome to the Cancer Biomarker Identifier. Monitor your analyses and explore results.',
      },
      common: {
        loading: 'Loading...',
        skipToContent: 'Skip to content',
      },
      auth: {
        signIn: 'Sign in to your account',
        createAccount: 'Create your account',
        passwordsMismatch: 'Passwords do not match',
        loginSuccess: 'Login successful!',
        registerSuccess: 'Registration successful!',
        unexpectedError: 'An unexpected error occurred',
      },
    },
  },
  es: {
    translation: {
      appName: 'Identificador de Biomarcadores de Cáncer',
      nav: {
        dashboard: 'Panel',
        upload: 'Cargar Datos',
        monitoring: 'Monitoreo',
        results: 'Resultados',
        reports: 'Reportes',
        clinical: 'Bases Clínicas',
        models: 'Modelos ML',
        settings: 'Configuración',
        complianceAdmin: 'Cumplimiento (admin)',
        toolsResources: 'Herramientas y Recursos',
      },
      header: {
        openMenu: 'Abrir menú',
        userMenu: 'Menú de usuario',
        profile: 'Perfil',
        signOut: 'Cerrar sesión',
        notifications: 'Notificaciones',
        language: 'Idioma',
      },
      dashboard: {
        title: 'Panel',
        subtitle:
          'Bienvenido al Identificador de Biomarcadores de Cáncer. Monitorea tus análisis y explora resultados.',
      },
      common: {
        loading: 'Cargando...',
        skipToContent: 'Saltar al contenido',
      },
      auth: {
        signIn: 'Inicia sesión en tu cuenta',
        createAccount: 'Crea tu cuenta',
        passwordsMismatch: 'Las contraseñas no coinciden',
        loginSuccess: 'Inicio de sesión exitoso',
        registerSuccess: 'Registro exitoso',
        unexpectedError: 'Ocurrió un error inesperado',
      },
    },
  },
};

i18n.use(initReactI18next).init({
  resources,
  lng:
    process.env.NODE_ENV === 'test'
      ? 'en'
      : (localStorage.getItem('locale') || 'en'),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
});

export default i18n;
