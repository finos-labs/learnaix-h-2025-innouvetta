// File: /local/chatbot/settings.php
<?php
defined('MOODLE_INTERNAL') || die();

if ($hassiteconfig) {
    $settings = new admin_settingpage('local_chatbot', get_string('settings', 'local_chatbot'));
    
    // API URL setting
    $settings->add(new admin_setting_configtext(
        'local_chatbot/api_url',
        get_string('api_url', 'local_chatbot'),
        get_string('api_url_desc', 'local_chatbot'),
        'http://localhost:5000',
        PARAM_URL
    ));
    
    // Enable file upload
    $settings->add(new admin_setting_configcheckbox(
        'local_chatbot/enable_file_upload',
        get_string('enable_file_upload', 'local_chatbot'),
        get_string('enable_file_upload_desc', 'local_chatbot'),
        1
    ));
    
    // Max file size
    $settings->add(new admin_setting_configtext(
        'local_chatbot/max_file_size',
        get_string('max_file_size', 'local_chatbot'),
        get_string('max_file_size_desc', 'local_chatbot'),
        '16',
        PARAM_INT
    ));
    
    // Allowed extensions
    $settings->add(new admin_setting_configtext(
        'local_chatbot/allowed_extensions',
        get_string('allowed_extensions', 'local_chatbot'),
        get_string('allowed_extensions_desc', 'local_chatbot'),
        'pdf,jpg,jpeg,png',
        PARAM_TEXT
    ));
    
    $ADMIN->add('localplugins', $settings);
}