// File: /local/chatbot/js/chat.js

M.local_chatbot = {
    config: null,
    sessionId: null,
    currentLanguage: 'en',
    
    init: function(Y, config) {
        this.config = config;
        this.sessionId = this.generateSessionId();
        this.currentLanguage = this.getStoredLanguage() || 'en';
        this.setupEventListeners();
        this.setupLanguageSelector();
        this.addWelcomeMessage();
        this.updateLanguageSelector();
    },
    
    generateSessionId: function() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    },
    
    getStoredLanguage: function() {
        return localStorage.getItem('chatbot_language') || 'en';
    },
    
    setStoredLanguage: function(lang) {
        localStorage.setItem('chatbot_language', lang);
    },
    
    setupEventListeners: function() {
        var self = this;
        
        // Send button
        document.getElementById('send-btn').addEventListener('click', function() {
            self.sendMessage();
        });
        
        // Enter key in textarea
        document.getElementById('message-input').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                self.sendMessage();
            }
        });
        
        // Auto-resize textarea
        document.getElementById('message-input').addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        
        // File upload
        if (this.config.enableFileUpload) {
            document.getElementById('file-upload-btn').addEventListener('click', function() {
                document.getElementById('file-input').click();
            });
            
            document.getElementById('file-input').addEventListener('change', function(e) {
                if (e.target.files.length > 0) {
                    self.uploadFile(e.target.files[0]);
                }
            });
        }
        
        // Reset chat
        document.getElementById('reset-chat').addEventListener('click', function() {
            self.resetChat();
        });
        
        // Language selector
        document.getElementById('language-selector').addEventListener('change', function(e) {
            self.changeLanguage(e.target.value);
        });
    },
    
    setupLanguageSelector: function() {
        var selector = document.getElementById('language-selector');
        selector.value = this.currentLanguage;
    },
    
    updateLanguageSelector: function() {
        document.getElementById('language-selector').value = this.currentLanguage;
    },
    
    addWelcomeMessage: function() {
        var welcomeMessages = {
            'en': "Hello! I'm your educational assistant. How can I help you today?",
            'hi': "नमस्ते! मैं आपका शैक्षणिक सहायक हूं। आज मैं आपकी कैसे मदद कर सकता हूं?",
            'es': "¡Hola! Soy tu asistente educativo. ¿Cómo puedo ayudarte hoy?",
            'fr': "Bonjour! Je suis votre assistant éducatif. Comment puis-je vous aider aujourd'hui?"
        };
        
        this.addMessage('bot', welcomeMessages[this.currentLanguage] || welcomeMessages['en']);
    },
    
    sendMessage: function() {
        var input = document.getElementById('message-input');
        var message = input.value.trim();
        
        if (!message) return;
        
        this.addMessage('user', message);
        input.value = '';
        input.style.height = 'auto';
        
        this.showTypingIndicator();
        
        // Send JSON data for text messages
        var requestData = {
            message: message,
            session_id: this.sessionId,
            language: this.currentLanguage
        };
        
        this.callAPIWithJSON('/chat', requestData);
    },
    
    uploadFile: function(file) {
        var self = this;
        
        // Check file size
        if (file.size > this.config.maxFileSize) {
            alert('File size exceeds maximum allowed size of ' + (this.config.maxFileSize / (1024 * 1024)) + 'MB');
            return;
        }
        
        // Check file extension
        var ext = file.name.split('.').pop().toLowerCase();
        if (this.config.allowedExtensions.indexOf(ext) === -1) {
            alert('File type not allowed. Allowed types: ' + this.config.allowedExtensions.join(', '));
            return;
        }
        
        this.addMessage('user', 'Uploading file: ' + file.name, true);
        this.showTypingIndicator();
        
        // Use FormData for file uploads
        var formData = new FormData();
        formData.append('file', file);
        formData.append('session_id', this.sessionId);
        formData.append('language', this.currentLanguage);
        
        this.callAPIWithFormData('/chat', formData);
        
        // Clear file input
        document.getElementById('file-input').value = '';
    },
    
    callAPIWithJSON: function(endpoint, data) {
        var self = this;
        
        fetch(this.config.apiUrl + endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            mode: 'cors',
            credentials: 'omit',
            body: JSON.stringify(data)
        })
        .then(response => {
            console.log('Response status:', response.status);
            console.log('Response headers:', response.headers);
            
            if (!response.ok) {
                throw new Error('HTTP error! status: ' + response.status + ' ' + response.statusText);
            }
            
            // Check if response is JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error('Response is not JSON');
            }
            
            return response.json();
        })
        .then(data => {
            console.log('API Response:', data);
            self.handleAPIResponse(data);
        })
        .catch(error => {
            console.error('Fetch Error Details:', error);
            self.handleAPIError(error);
        });
    },
    
    callAPIWithFormData: function(endpoint, formData) {
        var self = this;
        
        fetch(this.config.apiUrl + endpoint, {
            method: 'POST',
            mode: 'cors',
            credentials: 'omit',
            body: formData
        })
        .then(response => {
            console.log('File upload response status:', response.status);
            
            if (!response.ok) {
                throw new Error('HTTP error! status: ' + response.status + ' ' + response.statusText);
            }
            
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error('Response is not JSON');
            }
            
            return response.json();
        })
        .then(data => {
            console.log('File upload API Response:', data);
            self.handleAPIResponse(data);
        })
        .catch(error => {
            console.error('File upload Error Details:', error);
            self.handleAPIError(error);
        });
    },
    
    handleAPIResponse: function(data) {
        this.hideTypingIndicator();
        
        if (data.error) {
            this.addMessage('bot', 'Error: ' + data.error);
        } else {
            this.addMessage('bot', data.answer);
            
            // Update session info if provided
            if (data.session_id) {
                this.sessionId = data.session_id;
            }
            
            // Update language if changed
            if (data.language && data.language !== this.currentLanguage) {
                this.currentLanguage = data.language;
                this.setStoredLanguage(data.language);
                this.updateLanguageSelector();
            }
        }
    },
    
    handleAPIError: function(error) {
        this.hideTypingIndicator();
        console.error('API Error Details:', error);
        
        var errorMessage = '';
        
        if (error.message.includes('CORS')) {
            errorMessage = 'Connection blocked by CORS policy. Please check if the backend server is running on the correct URL: ' + this.config.apiUrl;
        } else if (error.message.includes('Failed to fetch')) {
            errorMessage = 'Cannot connect to the server. Please check if the backend is running at: ' + this.config.apiUrl;
        } else if (error.message.includes('HTTP error')) {
            errorMessage = 'Server error: ' + error.message;
        } else {
            var errorMessages = {
                'en': 'Sorry, I encountered an error. Please try again.',
                'hi': 'क्षमा करें, मुझे एक त्रुटि का सामना करना पड़ा। कृपया पुन: प्रयास करें।',
                'es': 'Lo siento, encontré un error. Por favor intenta de nuevo.',
                'fr': 'Désolé, j\'ai rencontré une erreur. Veuillez réessayer.'
            };
            errorMessage = errorMessages[this.currentLanguage] || errorMessages['en'];
        }
        
        this.addMessage('bot', errorMessage);
    },
    
    addMessage: function(sender, text, isFile) {
        var messagesContainer = document.getElementById('chat-messages');
        var messageDiv = document.createElement('div');
        messageDiv.className = 'message ' + sender;
        
        var avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.textContent = sender === 'user' ? '👤' : '🤖';
        
        var content = document.createElement('div');
        content.className = 'message-content';
        
        if (isFile) {
            content.innerHTML = '<div class="file-info">📎 ' + this.escapeHtml(text) + '</div>';
        } else {
            // Convert line breaks to HTML and handle basic formatting
            var formattedText = this.escapeHtml(text)
                .replace(/\n/g, '<br>')
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold
                .replace(/\*(.*?)\*/g, '<em>$1</em>'); // Italic
            
            content.innerHTML = formattedText;
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(content);
        messagesContainer.appendChild(messageDiv);
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    },
    
    showTypingIndicator: function() {
        document.getElementById('typing-indicator').style.display = 'flex';
        var messagesContainer = document.getElementById('chat-messages');
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    },
    
    hideTypingIndicator: function() {
        document.getElementById('typing-indicator').style.display = 'none';
    },
    
    resetChat: function() {
        var self = this;
        
        var requestData = {
            session_id: this.sessionId
        };
        
        this.callAPIWithJSON('/reset_session', requestData)
        .then(() => {
            // Clear chat messages
            document.getElementById('chat-messages').innerHTML = '';
            
            // Generate new session ID
            self.sessionId = self.generateSessionId();
            
            // Add welcome message
            self.addWelcomeMessage();
        })
        .catch(error => {
            console.error('Error resetting chat:', error);
            // Clear chat anyway
            document.getElementById('chat-messages').innerHTML = '';
            self.sessionId = self.generateSessionId();
            self.addWelcomeMessage();
        });
    },
    
    changeLanguage: function(newLang) {
        if (newLang === this.currentLanguage) return;
        
        this.currentLanguage = newLang;
        this.setStoredLanguage(newLang);
        
        var self = this;
        var requestData = {
            session_id: this.sessionId,
            language: newLang
        };
        
        this.callAPIWithJSON('/set_language', requestData)
        .then(() => {
            // Update UI language immediately
            self.updateUILanguage(newLang);
        })
        .catch(error => {
            console.error('Error changing language:', error);
            // Update UI anyway
            self.updateUILanguage(newLang);
        });
    },
    
    updateUILanguage: function(lang) {
        var translations = {
            'en': {
                'type_message': 'Type your message...',
                'send': 'Send',
                'reset_chat': 'Reset Chat',
                'upload_file': 'Upload File',
                'connecting': 'Connecting...'
            },
            'hi': {
                'type_message': 'अपना संदेश टाइप करें...',
                'send': 'भेजें',
                'reset_chat': 'चैट रीसेट करें',
                'upload_file': 'फ़ाइल अपलोड करें',
                'connecting': 'जुड़ रहा है...'
            },
            'es': {
                'type_message': 'Escribe tu mensaje...',
                'send': 'Enviar',
                'reset_chat': 'Reiniciar Chat',
                'upload_file': 'Subir Archivo',
                'connecting': 'Conectando...'
            },
            'fr': {
                'type_message': 'Tapez votre message...',
                'send': 'Envoyer',
                'reset_chat': 'Réinitialiser le Chat',
                'upload_file': 'Télécharger un Fichier',
                'connecting': 'Connexion...'
            }
        };
        
        var t = translations[lang] || translations['en'];
        
        // Update UI elements
        var messageInput = document.getElementById('message-input');
        if (messageInput) messageInput.placeholder = t['type_message'];
        
        var sendBtn = document.getElementById('send-btn');
        if (sendBtn) sendBtn.title = t['send'];
        
        var resetBtn = document.getElementById('reset-chat');
        if (resetBtn) resetBtn.textContent = t['reset_chat'];
        
        var uploadBtn = document.getElementById('file-upload-btn');
        if (uploadBtn) uploadBtn.title = t['upload_file'];
        
        var typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            var span = typingIndicator.querySelector('span:last-child');
            if (span) span.textContent = t['connecting'];
        }
    },
    
    escapeHtml: function(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};