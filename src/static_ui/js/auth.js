const API = '';

function saveToken(token) {
    localStorage.setItem('access_token', token);
}

function getToken() {
    return localStorage.getItem('access_token');
}

function clearToken() {
    localStorage.removeItem('access_token');
}

function authHeaders() {
    return {
        'Authorization': `Bearer ${getToken()}`
    };
}

function requireAuth() {
    if (!getToken()) {
        window.location.href = '/static/index.html';
    }
}

function logout() {
    clearToken();
    window.location.href = '/static/index.html';
}