<?php
require_once('../../config.php');
require_once($CFG->libdir . '/adminlib.php');

require_login();
require_capability('local/chatbot:use', context_system::instance());

$PAGE->set_context(context_system::instance());
$PAGE->set_url('/local/chatbot/index.php');
$PAGE->set_title(get_string('chatbot_title', 'local_chatbot'));
$PAGE->set_heading(get_string('chatbot_title', 'local_chatbot'));
$PAGE->set_pagelayout('standard');

// Include required JavaScript and CSS
$PAGE->requires->css('/local/chatbot/styles.css');
$PAGE->requires->js('/local/chatbot/js/chat.js');

// Get plugin settings
$api_url = get_config('local_chatbot', 'api_url') ?: 'http://localhost:5000';
$enable_file_upload = get_config('local_chatbot', 'enable_file_upload');
$max_file_size = get_config('local_chatbot', 'max_file_size') ?: 16;
$allowed_extensions = get_config('local_chatbot', 'allowed_extensions') ?: 'pdf,jpg,jpeg,png';

// Pass settings to JavaScript
$js_config = array(
    'apiUrl' => $api_url,
    'enableFileUpload' => $enable_file_upload,
    'maxFileSize' => $max_file_size * 1024 * 1024, // Convert to bytes
    'allowedExtensions' => explode(',', $allowed_extensions),
    'strings' => array(
        'type_message' => get_string('type_message', 'local_chatbot'),
        'send' => get_string('send', 'local_chatbot'),
        'upload_file' => get_string('upload_file', 'local_chatbot'),
        'reset_chat' => get_string('reset_chat', 'local_chatbot'),
        'language' => get_string('language', 'local_chatbot'),
        'connecting' => get_string('connecting', 'local_chatbot'),
        'file_uploaded' => get_string('file_uploaded', 'local_chatbot'),
        'file_upload_error' => get_string('file_upload_error', 'local_chatbot')
    )
);

$PAGE->requires->js_init_call('M.local_chatbot.init', array($js_config));

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

<div id="chatbot-container">
    <div id="chatbot-header">
        <h3><?php echo get_string('chatbot_title', 'local_chatbot'); ?></h3>
        <div id="chatbot-controls">
            <select id="language-selector">
                <option value="en">English</option>
                <option value="hi">हिंदी</option>
                <option value="es">Español</option>
                <option value="fr">Français</option>
            </select>
            <button id="reset-chat" class="btn btn-secondary"><?php echo get_string('reset_chat', 'local_chatbot'); ?></button>
        </div>
    </div>

    <div id="chat-messages"></div>

    <div id="chat-input-container">
        <?php if ($enable_file_upload): ?>
        <div id="file-upload-container">
            <input type="file" id="file-input" accept=".<?php echo str_replace(',', ',.', $allowed_extensions); ?>" style="display: none;">
            <button id="file-upload-btn" class="btn btn-outline-secondary" title="<?php echo get_string('upload_file', 'local_chatbot'); ?>">
                📎
            </button>
        </div>
        <?php endif; ?>

        <div id="message-input-container">
            <textarea id="message-input" placeholder="<?php echo get_string('type_message', 'local_chatbot'); ?>" rows="1"></textarea>
            <button id="send-btn" class="btn btn-primary"><?php echo get_string('send', 'local_chatbot'); ?></button>
        </div>
    </div>

    <div id="typing-indicator" style="display: none;">
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <span><?php echo get_string('connecting', 'local_chatbot'); ?></span>
    </div>
</div>

<?php echo $OUTPUT->footer(); ?>