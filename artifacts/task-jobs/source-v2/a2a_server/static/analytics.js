/**
 * CodeTether First-Party Analytics
 * 
 * Lightweight tracking snippet for first-party event collection.
 * 
 * Usage:
 *   <script src="https://api.codetether.run/static/analytics.js"></script>
 *   <script>
 *     ct.init({ endpoint: 'https://api.codetether.run' });
 *     ct.page();  // Track page view
 *     ct.track('signup_started', { email: 'user@example.com' });
 *     ct.identify('user-123', { email: 'user@example.com' });
 *   </script>
 */
(function(window) {
  'use strict';

  // Configuration
  var config = {
    endpoint: '',
    debug: false
  };

  // State
  var anonymousId = null;
  var userId = null;
  var sessionId = null;

  // Generate UUID v4
  function uuid() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0;
      var v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  // Get or create anonymous ID
  function getAnonymousId() {
    if (anonymousId) return anonymousId;
    
    try {
      anonymousId = localStorage.getItem('ct_anon_id');
      if (!anonymousId) {
        anonymousId = uuid();
        localStorage.setItem('ct_anon_id', anonymousId);
      }
    } catch (e) {
      anonymousId = uuid();
    }
    return anonymousId;
  }

  // Get or create session ID
  function getSessionId() {
    if (sessionId) return sessionId;
    
    try {
      sessionId = sessionStorage.getItem('ct_session_id');
      if (!sessionId) {
        sessionId = uuid();
        sessionStorage.setItem('ct_session_id', sessionId);
      }
    } catch (e) {
      sessionId = uuid();
    }
    return sessionId;
  }

  // Get UTM parameters from URL
  function getUtmParams() {
    var params = new URLSearchParams(window.location.search);
    return {
      utm_source: params.get('utm_source'),
      utm_medium: params.get('utm_medium'),
      utm_campaign: params.get('utm_campaign'),
      utm_term: params.get('utm_term'),
      utm_content: params.get('utm_content'),
      x_click_id: params.get('twclid'),
      fb_click_id: params.get('fbclid'),
      google_click_id: params.get('gclid')
    };
  }

  // Send event to server
  function send(eventType, properties, callback) {
    var utm = getUtmParams();
    var payload = {
      event_type: eventType,
      anonymous_id: getAnonymousId(),
      user_id: userId,
      session_id: getSessionId(),
      page_url: window.location.href,
      page_title: document.title,
      referrer: document.referrer,
      utm_source: utm.utm_source,
      utm_medium: utm.utm_medium,
      utm_campaign: utm.utm_campaign,
      utm_term: utm.utm_term,
      utm_content: utm.utm_content,
      x_click_id: utm.x_click_id,
      fb_click_id: utm.fb_click_id,
      google_click_id: utm.google_click_id,
      properties: properties || {},
      timestamp: new Date().toISOString()
    };

    if (config.debug) {
      console.log('[CT] Tracking:', eventType, payload);
    }

    var xhr = new XMLHttpRequest();
    xhr.open('POST', config.endpoint + '/v1/analytics/track', true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function() {
      if (xhr.readyState === 4 && callback) {
        callback(xhr.status === 200 ? null : xhr.responseText, xhr.response);
      }
    };
    xhr.send(JSON.stringify(payload));
  }

  // Public API
  var ct = {
    /**
     * Initialize the tracker
     * @param {Object} options - { endpoint: string, debug: boolean }
     */
    init: function(options) {
      config.endpoint = options.endpoint || '';
      config.debug = options.debug || false;
      
      if (config.debug) {
        console.log('[CT] Initialized with endpoint:', config.endpoint);
        console.log('[CT] Anonymous ID:', getAnonymousId());
      }
    },

    /**
     * Track a page view
     */
    page: function(callback) {
      send('page_view', {}, callback);
    },

    /**
     * Track a custom event
     * @param {string} eventType - Event name
     * @param {Object} properties - Event properties
     * @param {Function} callback - Optional callback
     */
    track: function(eventType, properties, callback) {
      send(eventType, properties, callback);
    },

    /**
     * Link anonymous ID to a known user
     * @param {string} id - User ID
     * @param {Object} traits - User traits (email, name, etc.)
     */
    identify: function(id, traits, callback) {
      userId = id;
      
      var payload = {
        anonymous_id: getAnonymousId(),
        user_id: id,
        email: traits ? traits.email : null,
        traits: traits || {}
      };

      if (config.debug) {
        console.log('[CT] Identify:', id, traits);
      }

      var xhr = new XMLHttpRequest();
      xhr.open('POST', config.endpoint + '/v1/analytics/identify', true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.onreadystatechange = function() {
        if (xhr.readyState === 4 && callback) {
          callback(xhr.status === 200 ? null : xhr.responseText, xhr.response);
        }
      };
      xhr.send(JSON.stringify(payload));
    },

    /**
     * Get the anonymous ID
     */
    getAnonymousId: getAnonymousId,

    /**
     * Reset the user (logout)
     */
    reset: function() {
      userId = null;
      sessionId = null;
      try {
        sessionStorage.removeItem('ct_session_id');
      } catch (e) {}
    }
  };

  // Auto-initialize if data attribute present
  var script = document.currentScript;
  if (script && script.dataset.endpoint) {
    ct.init({ 
      endpoint: script.dataset.endpoint,
      debug: script.dataset.debug === 'true'
    });
  }

  // Expose globally
  window.ct = ct;

})(window);
