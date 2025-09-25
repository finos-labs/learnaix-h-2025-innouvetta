// File: /local/chatbot/js/assignments.js

M.local_chatbot_assignments = {
  config: null,
  assignments: [],

  init: function (Y, config) {
    this.config = config;
    this.setupEventListeners();
    this.loadAssignments();
  },

  setupEventListeners: function () {
    var self = this;

    // Retry button
    document.getElementById("retry-btn").addEventListener("click", function () {
      self.loadAssignments();
    });

    // Modal close handlers
    document.querySelectorAll(".modal-close").forEach(function (closeBtn) {
      closeBtn.addEventListener("click", function () {
        self.closeModal("upload-modal");
        self.closeModal("success-modal");
      });
    });

    // Modal cancel button
    var cancelBtn = document.querySelector(".modal-cancel");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        self.closeModal("upload-modal");
      });
    }

    // Click outside modal to close
    window.addEventListener("click", function (event) {
      if (event.target.classList.contains("modal")) {
        self.closeModal("upload-modal");
        self.closeModal("success-modal");
      }
    });

    // Solution upload form
    document
      .getElementById("solution-upload-form")
      .addEventListener("submit", function (e) {
        e.preventDefault();
        self.submitSolution();
      });

    // File input change handler for validation
    document
      .getElementById("solution-file")
      .addEventListener("change", function (e) {
        self.validateFile(e.target);
      });
  },

  loadAssignments: function () {
    var self = this;

    // Show loading state
    this.showLoadingState();

    fetch(this.config.apiUrl + "/assignments", {
      method: "GET",
      headers: {
        Accept: "application/json",
      },
      mode: "cors",
      credentials: "omit",
    })
      .then(function (response) {
        console.log("Assignments API response status:", response.status);
        
        if (!response.ok) {
          throw new Error("HTTP error! status: " + response.status);
        }
        
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          throw new Error("Response is not JSON");
        }
        
        return response.json();
      })
      .then(function (data) {
        console.log("Assignments loaded:", data);
        self.assignments = data.assignments || [];
        self.renderAssignments();
      })
      .catch(function (error) {
        console.error("Error loading assignments:", error);
        self.showError("Failed to load assignments. Please check if the backend server is running at: " + self.config.apiUrl);
      });
  },

  showLoadingState: function () {
    document.getElementById("loading-indicator").style.display = "block";
    document.getElementById("assignments-table-container").style.display = "none";
    document.getElementById("no-assignments").style.display = "none";
    document.getElementById("error-section").style.display = "none";
  },

  renderAssignments: function () {
    var self = this;

    // Hide loading
    document.getElementById("loading-indicator").style.display = "none";

    if (this.assignments.length === 0) {
      document.getElementById("no-assignments").style.display = "block";
      this.updateStats(0, 0, 0);
      return;
    }

    // Show table
    document.getElementById("assignments-table-container").style.display = "block";

    var tbody = document.getElementById("assignments-tbody");
    tbody.innerHTML = "";

    var submittedCount = 0;
    var pendingCount = 0;

    this.assignments.forEach(function (assignment) {
      var row = document.createElement("tr");
      row.className = "assignment-row";

      // Course
      var courseCell = document.createElement("td");
      courseCell.textContent = assignment.course_name;
      courseCell.className = "course-cell";
      row.appendChild(courseCell);

      // Assignment Name
      var nameCell = document.createElement("td");
      nameCell.textContent = assignment.assignment_name;
      nameCell.className = "assignment-name-cell";
      row.appendChild(nameCell);

      // Assignment PDF
      var pdfCell = document.createElement("td");
      var pdfLink = document.createElement("a");
      pdfLink.href = self.convertToGoogleDriveViewer(assignment.assignment_pdf);
      pdfLink.target = "_blank";
      pdfLink.className = "pdf-link";
      pdfLink.innerHTML = '📄 View PDF';
      pdfCell.appendChild(pdfLink);
      row.appendChild(pdfCell);

      // Status
      var statusCell = document.createElement("td");
      var statusBadge = document.createElement("span");
      if (assignment.solution_pdf && assignment.solution_pdf.trim() !== '') {
        statusBadge.className = "status-badge submitted";
        statusBadge.textContent = "Submitted";
        submittedCount++;
      } else {
        statusBadge.className = "status-badge pending";
        statusBadge.textContent = "Pending";
        pendingCount++;
      }
      statusCell.appendChild(statusBadge);
      row.appendChild(statusCell);

      // Score
      var scoreCell = document.createElement("td");
      if (assignment.score !== null && assignment.score !== undefined) {
        var scoreSpan = document.createElement("span");
        scoreSpan.className = "score-display";
        scoreSpan.textContent = assignment.score + "/100";
        scoreCell.appendChild(scoreSpan);
      } else {
        scoreCell.textContent = "--";
        scoreCell.className = "no-score";
      }
      row.appendChild(scoreCell);

      // Actions
      var actionsCell = document.createElement("td");
      actionsCell.className = "actions-cell";

      if (assignment.solution_pdf && assignment.solution_pdf.trim() !== '') {
        // View solution button
        var viewSolutionBtn = document.createElement("button");
        viewSolutionBtn.className = "btn btn-outline-primary btn-sm";
        viewSolutionBtn.innerHTML = "👁️ View Solution";
        viewSolutionBtn.addEventListener("click", function () {
          window.open(
            self.convertToGoogleDriveViewer(assignment.solution_pdf),
            "_blank"
          );
        });
        actionsCell.appendChild(viewSolutionBtn);
      } else {
        // Submit solution button
        var submitBtn = document.createElement("button");
        submitBtn.className = "btn btn-primary btn-sm";
        submitBtn.innerHTML = "📤 Submit Solution";
        submitBtn.addEventListener("click", function () {
          self.showUploadModal(assignment);
        });
        actionsCell.appendChild(submitBtn);
      }

      row.appendChild(actionsCell);
      tbody.appendChild(row);
    });

    this.updateStats(this.assignments.length, submittedCount, pendingCount);
  },

  updateStats: function (total, submitted, pending) {
    document.getElementById("total-assignments").textContent = total;
    document.getElementById("submitted-count").textContent = submitted;
    document.getElementById("pending-count").textContent = pending;
  },

  showError: function (message) {
    document.getElementById("loading-indicator").style.display = "none";
    document.getElementById("assignments-table-container").style.display = "none";
    document.getElementById("no-assignments").style.display = "none";
    document.getElementById("error-section").style.display = "block";
    document.getElementById("error-message").textContent = message;
  },

  convertToGoogleDriveViewer: function (driveUrl) {
    if (!driveUrl) return '#';
    
    // Handle different Google Drive URL formats
    var fileId = '';
    
    if (driveUrl.includes('/d/')) {
      // Format: https://drive.google.com/file/d/FILE_ID/view
      fileId = driveUrl.split("/d/")[1].split("/")[0];
    } else if (driveUrl.includes('id=')) {
      // Format: https://drive.google.com/open?id=FILE_ID
      fileId = driveUrl.split('id=')[1].split('&')[0];
    } else if (driveUrl.match(/^[a-zA-Z0-9_-]+$/)) {
      // Direct file ID
      fileId = driveUrl;
    }
    
    if (fileId) {
      return "https://drive.google.com/file/d/" + fileId + "/preview";
    }
    
    return driveUrl; // Return original URL if parsing fails
  },

  showUploadModal: function (assignment) {
    document.getElementById("modal-assignment-id").value = assignment.id;
    var modalTitle = document.querySelector("#upload-modal .modal h3");
    if (modalTitle) {
      modalTitle.textContent = "Submit Solution for: " + assignment.assignment_name;
    }
    this.showModal("upload-modal");
  },

  showModal: function (modalId) {
    var modal = document.getElementById(modalId);
    if (modal) {
      modal.style.display = "flex";
      document.body.style.overflow = "hidden";
      
      // Focus trap for accessibility
      var focusableElements = modal.querySelectorAll('button, input, select, textarea');
      if (focusableElements.length > 0) {
        focusableElements[0].focus();
      }
    }
  },

  closeModal: function (modalId) {
    var modal = document.getElementById(modalId);
    if (modal) {
      modal.style.display = "none";
      document.body.style.overflow = "auto";
    }

    // Reset forms
    if (modalId === "upload-modal") {
      var form = document.getElementById("solution-upload-form");
      if (form) {
        form.reset();
      }
      var progress = document.getElementById("upload-progress");
      if (progress) {
        progress.style.display = "none";
      }
    }
  },

  validateFile: function (fileInput) {
    var file = fileInput.files[0];
    var errorMsg = "";

    if (file) {
      // Check file type
      if (file.type !== "application/pdf") {
        errorMsg = "Please select a valid PDF file.";
      }
      // Check file size (16MB limit)
      else if (file.size > 16 * 1024 * 1024) {
        errorMsg = "File size must be less than 16MB.";
      }
    }

    // Display error or clear previous error
    var existingError = fileInput.parentNode.querySelector('.file-error');
    if (existingError) {
      existingError.remove();
    }

    if (errorMsg) {
      var errorDiv = document.createElement('div');
      errorDiv.className = 'file-error';
      errorDiv.style.color = '#dc3545';
      errorDiv.style.fontSize = '0.8rem';
      errorDiv.style.marginTop = '5px';
      errorDiv.textContent = errorMsg;
      fileInput.parentNode.appendChild(errorDiv);
      return false;
    }

    return true;
  },

  submitSolution: function () {
    var self = this;
    var form = document.getElementById("solution-upload-form");
    var fileInput = document.getElementById("solution-file");
    var assignmentId = document.getElementById("modal-assignment-id").value;

    if (!fileInput.files.length) {
      alert("Please select a PDF file to upload.");
      return;
    }

    // Validate file
    if (!this.validateFile(fileInput)) {
      return;
    }

    var file = fileInput.files[0];

    // Show progress
    var progressDiv = document.getElementById("upload-progress");
    var submitBtn = form.querySelector('button[type="submit"]');
    
    if (progressDiv) progressDiv.style.display = "block";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting...";
    }

    // Create FormData
    var formData = new FormData();
    formData.append("assignment_id", assignmentId);
    formData.append("solution_file", file);

    fetch(this.config.apiUrl + "/submit_solution", {
      method: "POST",
      mode: "cors",
      credentials: "omit",
      body: formData,
    })
      .then(function (response) {
        console.log("Submit solution response status:", response.status);
        
        if (!response.ok) {
          return response.text().then(function(text) {
            throw new Error("HTTP error! status: " + response.status + " - " + text);
          });
        }
        
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
          throw new Error("Response is not JSON");
        }
        
        return response.json();
      })
      .then(function (data) {
        console.log("Solution submitted successfully:", data);

        // Close upload modal
        self.closeModal("upload-modal");

        // Show success modal with score
        var scoreElement = document.getElementById("final-score");
        var feedbackElement = document.getElementById("feedback-content");
        
        if (scoreElement) {
          scoreElement.textContent = data.score || "--";
        }
        if (feedbackElement) {
          feedbackElement.innerHTML = self.formatFeedback(data.feedback || "No feedback available.");
        }

        self.showModal("success-modal");

        // Reload assignments to reflect changes
        self.loadAssignments();
      })
      .catch(function (error) {
        console.error("Error submitting solution:", error);
        alert("Error submitting solution: " + error.message);
      })
      .finally(function () {
        // Reset button and hide progress
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "Submit Solution";
        }
        if (progressDiv) {
          progressDiv.style.display = "none";
        }
      });
  },

  formatFeedback: function (feedback) {
    if (!feedback) return "No feedback available.";
    
    // Basic formatting for the feedback text
    return feedback
      .replace(/\n/g, "<br>")
      .replace(/SCORE\s*:/gi, "<strong>SCORE:</strong>")
      .replace(/FEEDBACK\s*:/gi, "<strong>FEEDBACK:</strong>")
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>") // Bold
      .replace(/\*(.*?)\*/g, "<em>$1</em>") // Italic
      .replace(/(\d+)\/100/g, "<span class='score-highlight'>$1/100</span>"); // Highlight scores
  },

  // Utility function to handle API errors gracefully
  handleApiError: function (error) {
    var message = "An error occurred. Please try again.";
    
    if (error.message.includes("Failed to fetch")) {
      message = "Cannot connect to server. Please check if the backend is running at: " + this.config.apiUrl;
    } else if (error.message.includes("HTTP error")) {
      message = "Server error: " + error.message;
    } else if (error.message.includes("not JSON")) {
      message = "Invalid server response. Please check server configuration.";
    }
    
    return message;
  }
};