'use strict';

const getAccessToken = async (z, bundle) => {
  const response = await z.request({
    url: 'https://auth.quantum-forge.io/realms/quantum-forge/protocol/openid-connect/token',
    method: 'POST',
    body: {
      grant_type: 'authorization_code',
      code: bundle.inputData.code,
      client_id: process.env.CLIENT_ID,
      client_secret: process.env.CLIENT_SECRET,
      redirect_uri: bundle.inputData.redirect_uri,
    },
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });

  if (response.status !== 200) {
    throw new z.errors.Error('Unable to fetch access token', 'GetAccessTokenError', response.status);
  }

  return {
    access_token: response.data.access_token,
    refresh_token: response.data.refresh_token,
    expires_in: response.data.expires_in,
  };
};

const refreshAccessToken = async (z, bundle) => {
  const response = await z.request({
    url: 'https://auth.quantum-forge.io/realms/quantum-forge/protocol/openid-connect/token',
    method: 'POST',
    body: {
      grant_type: 'refresh_token',
      refresh_token: bundle.authData.refresh_token,
      client_id: process.env.CLIENT_ID,
      client_secret: process.env.CLIENT_SECRET,
    },
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
  });

  if (response.status !== 200) {
    throw new z.errors.RefreshAuthError();
  }

  return {
    access_token: response.data.access_token,
    refresh_token: response.data.refresh_token,
  };
};

const testAuth = async (z, bundle) => {
  const response = await z.request({
    url: 'https://auth.quantum-forge.io/realms/quantum-forge/protocol/openid-connect/userinfo',
  });

  if (response.status !== 200) {
    throw new z.errors.Error('Authentication test failed', 'AuthTestError', response.status);
  }

  return response.data;
};

module.exports = {
  type: 'oauth2',
  
  oauth2Config: {
    authorizeUrl: {
      url: 'https://auth.quantum-forge.io/realms/quantum-forge/protocol/openid-connect/auth',
      params: {
        client_id: '{{process.env.CLIENT_ID}}',
        state: '{{bundle.inputData.state}}',
        redirect_uri: '{{bundle.inputData.redirect_uri}}',
        response_type: 'code',
        scope: 'openid email profile',
      },
    },
    
    getAccessToken,
    refreshAccessToken,
    autoRefresh: true,
  },

  test: testAuth,

  connectionLabel: '{{email}}',
};
