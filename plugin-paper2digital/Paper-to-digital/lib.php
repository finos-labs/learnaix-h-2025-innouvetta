<?php
// This file is part of Moodle - http://moodle.org/

defined('MOODLE_INTERNAL') || die();

/**
 * Add the chatbot to the navigation
 */
function local_aichatbot_extend_navigation(global_navigation $nav) {
    global $USER, $PAGE;
    
    if (isloggedin() && !isguestuser()) {
        $chatbotnode = $nav->add(
            get_string('chatbot', 'local_aichatbot'),
            new moodle_url('/local/aichatbot/index.php'),
            navigation_node::TYPE_CUSTOM,
            null,
            'aichatbot',
            new pix_icon('i/chatbot', 'Chatbot', 'core')
        );
        $chatbotnode->showinflatnavigation = true;
    }
}

/**
 * Hook to add chatbot widget to all pages
 */
function local_aichatbot_before_footer() {
    global $PAGE, $USER;
    
    if (isloggedin() && !isguestuser()) {
        $PAGE->requires->js('/local/aichatbot/js/chatbot-widget.js');
        $PAGE->requires->css('/local/aichatbot/styles.css');
    }
}