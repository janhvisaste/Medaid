const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api';

interface SignupData {
  email: string;
  password: string;
  confirm_password?: string;
  first_name?: string;
  last_name?: string;
}

interface LoginData {
  email: string;
  password: string;
}

interface AuthResponse {
  access: string;
  refresh: string;
  user: {
    id: number;
    email: string;
    first_name?: string;
    last_name?: string;
  };
}

class AuthService {
  private token: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    this.token = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
  }

  async signup(data: SignupData): Promise<AuthResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/signup/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json();
        // DRF returns errors as {'field': ['error msg']} or {'non_field_errors': ['msg']}
        const errorMessage = errorData.detail 
          || errorData.non_field_errors?.[0]
          || Object.values(errorData).flat()[0]
          || 'Signup failed';
        throw new Error(String(errorMessage));
      }

      const result = await response.json();
      this.setTokens(result.access, result.refresh, result.user);
      return result;
    } catch (error) {
      console.error('Signup error:', error);
      throw error;
    }
  }

  async login(data: LoginData): Promise<AuthResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = errorData.detail
          || errorData.non_field_errors?.[0]
          || Object.values(errorData).flat()[0]
          || 'Login failed';
        throw new Error(String(errorMessage));
      }

      const result = await response.json();
      this.setTokens(result.access, result.refresh, result.user);
      return result;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  }

  async logout(): Promise<void> {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      await fetch(`${API_BASE_URL}/auth/logout/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${this.token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh: refreshToken }),
      });
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      this.clearTokens();
    }
  }

  private setTokens(access: string, refresh: string, user?: any): void {
    this.token = access;
    this.refreshToken = refresh;
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    if (user) {
      localStorage.setItem('user', JSON.stringify(user));
    }
  }

  private clearTokens(): void {
    this.token = null;
    this.refreshToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
  }

  getUser(): any {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
  }

  getToken(): string | null {
    // Always read from localStorage to get the latest token
    this.token = localStorage.getItem('access_token');
    return this.token;
  }

  isAuthenticated(): boolean {
    // Always check localStorage for the latest token
    const token = localStorage.getItem('access_token');
    return token !== null && token !== '';
  }

  getAuthHeaders(): HeadersInit {
    const token = this.getToken();
    return {
      'Content-Type': 'application/json',
      ...(token && { 'Authorization': `Bearer ${token}` }),
    };
  }
}

const authService = new AuthService();
export default authService;
