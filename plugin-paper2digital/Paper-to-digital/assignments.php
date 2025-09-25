<?php
require_once('../../config.php');
require_once($CFG->libdir . '/adminlib.php');

require_login();
require_capability('local/chatbot:use', context_system::instance());

$PAGE->set_context(context_system::instance());
$PAGE->set_url('/local/chatbot/assignments.php');
$PAGE->set_title('Assignments Due - ' . get_string('chatbot_title', 'local_chatbot'));
$PAGE->set_heading('Assignments Due');
$PAGE->set_pagelayout('standard');

// Include required JavaScript and CSS
$PAGE->requires->css('/local/chatbot/styles.css');
$PAGE->requires->js('/local/chatbot/js/assignments.js');

// Get API URL from plugin settings
$api_url = get_config('local_chatbot', 'api_url') ?: 'http://localhost:5000';

// Pass API URL to JavaScript
$js_config = array(
    'apiUrl' => $api_url,
    'strings' => array(
        'loading' => 'Loading assignments...',
        'no_assignments' => 'No assignments found',
        'error_loading' => 'Error loading assignments',
        'submit_solution' => 'Submit Solution',
        'view_solution' => 'View Solution',
        'view_assignment' => 'View Assignment',
        'score' => 'Score',
        'not_submitted' => 'Not Submitted',
        'submitted' => 'Submitted'
    )
);

$PAGE->requires->js_init_call('M.local_chatbot_assignments.init', array($js_config));

echo $OUTPUT->header();
?>

<!-- Navigation buttons -->
<div class="chatbot-navigation">
    <a href="<?php echo new moodle_url('/local/chatbot/index.php'); ?>" 
       class="nav-button <?php echo basename($_SERVER['PHP_SELF']) == 'index.php' ? 'active' : ''; ?>">
        💬 Chat Assistant
    </a>
    <a href="<?php echo new moodle_url('/local/chatbot/assignments.php'); ?>" 
       class="nav-button <?php echo basename($_SERVER['PHP_SELF']) == 'assignments.php' ? 'active' : ''; ?>">
        📝 Assignments Due
    </a>
</div>

<div id="assignments-container">
    <div class="assignments-header">
        <h2>📝 Assignments Due</h2>
        <div class="assignments-stats">
            <span id="total-assignments">0</span> assignments | 
            <span id="submitted-count">0</span> submitted | 
            <span id="pending-count">0</span> pending
        </div>
    </div>

    <div id="loading-indicator" class="loading-section">
        <div class="loading-spinner"></div>
        <p>Loading assignments...</p>
    </div>

    <div id="assignments-table-container" style="display: none;">
        <table id="assignments-table" class="assignments-table">
            <thead>
                <tr>
                    <th>Course</th>
                    <th>Assignment</th>
                    <th>Assignment PDF</th>
                    <th>Status</th>
                    <th>Score</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody id="assignments-tbody">
                <!-- Assignments will be loaded here -->
            </tbody>
        </table>
    </div>

    <div id="no-assignments" class="no-data-section" style="display: none;">
        <div class="no-data-icon">📋</div>
        <h3>No Assignments Found</h3>
        <p>There are currently no assignments available.</p>
    </div>

    <div id="error-section" class="error-section" style="display: none;">
        <div class="error-icon">⚠️</div>
        <h3>Error Loading Assignments</h3>
        <p id="error-message">Unable to load assignments. Please try again.</p>
        <button id="retry-btn" class="btn btn-primary">Retry</button>
    </div>
</div>

<!-- File Upload Modal -->
<div id="upload-modal" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="modal-header">
            <h3>Submit Solution</h3>
            <span class="modal-close">&times;</span>
        </div>
        <div class="modal-body">
            <form id="solution-upload-form" enctype="multipart/form-data">
                <input type="hidden" id="modal-assignment-id" name="assignment_id">
                
                <div class="form-group">
                    <label for="solution-file">Select Solution PDF:</label>
                    <input type="file" id="solution-file" name="solution_file" accept=".pdf" required>
                    <small class="form-text">Only PDF files are allowed (max 16MB)</small>
                </div>
                
                <div class="modal-progress" id="upload-progress" style="display: none;">
                    <div class="progress-bar">
                        <div class="progress-fill"></div>
                    </div>
                    <p>Uploading and processing...</p>
                </div>
                
                <div class="modal-actions">
                    <button type="button" class="btn btn-secondary modal-cancel">Cancel</button>
                    <button type="submit" class="btn btn-primary">Submit Solution</button>
                </div>
            </form>
        </div>
    </div>
</div>

<!-- Success Modal -->
<div id="success-modal" class="modal" style="display: none;">
    <div class="modal-content">
        <div class="modal-header">
            <h3>Solution Submitted Successfully!</h3>
            <span class="modal-close">&times;</span>
        </div>
        <div class="modal-body">
            <div class="success-icon">✅</div>
            <div id="score-display" class="score-display">
                <h4>Your Score: <span id="final-score">--</span>/100</h4>
            </div>
            <div id="feedback-display" class="feedback-display">
                <h5>Feedback:</h5>
                <div id="feedback-content"></div>
            </div>
            <div class="modal-actions">
                <button type="button" class="btn btn-primary modal-close">Close</button>
            </div>
        </div>
    </div>
</div>

<?php echo $OUTPUT->footer(); ?>