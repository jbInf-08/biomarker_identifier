import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { FlaskConical, Eye, EyeOff, Mail, Lock } from 'lucide-react';
import toast from 'react-hot-toast';
import { useTranslation } from 'react-i18next';

const Login = () => {
  const [isLogin, setIsLogin] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
    institution: '',
    role: 'researcher',
  });
  const [loading, setLoading] = useState(false);
  const { t } = useTranslation();
  
  const { login, register, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

  const handleInputChange = (e) => {
    setFormData(prev => ({
      ...prev,
      [e.target.name]: e.target.value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      let result;
      
      if (isLogin) {
        result = await login(formData.email, formData.password);
      } else {
        if (formData.password !== formData.confirmPassword) {
          toast.error(t('auth.passwordsMismatch'));
          setLoading(false);
          return;
        }
        
        result = await register({
          name: formData.name,
          email: formData.email,
          password: formData.password,
          institution: formData.institution,
          role: formData.role,
        });
      }

      if (result.success) {
        toast.success(isLogin ? t('auth.loginSuccess') : t('auth.registerSuccess'));
        navigate('/');
      } else {
        toast.error(result.error);
      }
    } catch (error) {
      toast.error(t('auth.unexpectedError'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        {/* Header */}
        <div className="text-center">
          <div className="flex justify-center">
            <div className="h-16 w-16 bg-primary-600 rounded-xl flex items-center justify-center">
              <FlaskConical className="h-8 w-8 text-white" />
            </div>
          </div>
          <h2 className="mt-6 text-3xl font-bold text-gray-900">
            {isLogin ? t('auth.signIn') : t('auth.createAccount')}
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            {isLogin ? (
              <>
                Or{' '}
                <button
                  type="button"
                  onClick={() => setIsLogin(false)}
                  className="font-medium text-primary-600 hover:text-primary-500"
                >
                  create a new account
                </button>
              </>
            ) : (
              <>
                Or{' '}
                <button
                  type="button"
                  onClick={() => setIsLogin(true)}
                  className="font-medium text-primary-600 hover:text-primary-500"
                >
                  sign in to existing account
                </button>
              </>
            )}
          </p>
        </div>

        {/* Form */}
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          <div className="space-y-4">
            {!isLogin && (
              <div>
                <label htmlFor="name" className="label">
                  Full Name
                </label>
                <div className="relative">
                  <input
                    id="name"
                    name="name"
                    type="text"
                    required={!isLogin}
                    className="input-field pl-10"
                    placeholder="Enter your full name"
                    value={formData.name}
                    onChange={handleInputChange}
                  />
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-gray-400" />
                  </div>
                </div>
              </div>
            )}

            <div>
              <label htmlFor="email" className="label">
                Email Address
              </label>
              <div className="relative">
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  className="input-field pl-10"
                  placeholder="Enter your email"
                  value={formData.email}
                  onChange={handleInputChange}
                />
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-gray-400" />
                </div>
              </div>
            </div>

            {!isLogin && (
              <>
                <div>
                  <label htmlFor="institution" className="label">
                    Institution
                  </label>
                  <input
                    id="institution"
                    name="institution"
                    type="text"
                    className="input-field"
                    placeholder="Enter your institution"
                    value={formData.institution}
                    onChange={handleInputChange}
                  />
                </div>

                <div>
                  <label htmlFor="role" className="label">
                    Role
                  </label>
                  <select
                    id="role"
                    name="role"
                    className="input-field"
                    value={formData.role}
                    onChange={handleInputChange}
                  >
                    <option value="researcher">Researcher</option>
                    <option value="clinician">Clinician</option>
                    <option value="bioinformatician">Bioinformatician</option>
                    <option value="student">Student</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </>
            )}

            <div>
              <label htmlFor="password" className="label">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  className="input-field pl-10 pr-10"
                  placeholder="Enter your password"
                  value={formData.password}
                  onChange={handleInputChange}
                />
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Lock className="h-5 w-5 text-gray-400" />
                </div>
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5 text-gray-400" />
                  ) : (
                    <Eye className="h-5 w-5 text-gray-400" />
                  )}
                </button>
              </div>
            </div>

            {!isLogin && (
              <div>
                <label htmlFor="confirmPassword" className="label">
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showPassword ? 'text' : 'password'}
                    required={!isLogin}
                    className="input-field pl-10"
                    placeholder="Confirm your password"
                    value={formData.confirmPassword}
                    onChange={handleInputChange}
                  />
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Lock className="h-5 w-5 text-gray-400" />
                  </div>
                </div>
              </div>
            )}
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full flex justify-center py-3 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-primary-600 hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              ) : (
                isLogin ? 'Sign in' : 'Create account'
              )}
            </button>
          </div>

          <div className="text-center">
            <p className="text-xs text-gray-500">
              By continuing, you agree to our Terms of Service and Privacy Policy.
            </p>
          </div>
        </form>
      </div>
    </div>
  );
};

export default Login;
