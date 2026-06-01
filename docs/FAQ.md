# Morpheus Video Studio FAQ

### How to integrate custom local workflows?

If you want to integrate your own ComfyUI workflows, please follow these specifications:

1.  **Run Locally First**: Ensure the workflow runs correctly in your local ComfyUI.
2.  **Parameter Binding**: Find the Text node (CLIP Text Encode or similar text input node) where prompt words need to be dynamically passed by the program.
    -   Edit the **Title** of that node.
    -   Change the title to `$prompt.text!` or `$prompt.value!` (depending on the input type accepted by the node).
     <img src="https://github.com/user-attachments/assets/ddb1962c-9272-486f-84ab-8019c3fb5bf4" width="600" alt="参数绑定示例" />

    -   *Reference Example: Check the editing method of existing JSON files in the `workflows/selfhost/` directory.*
3.  **Export Format**: Export the modified workflow as **API Format** (Save (API Format)).
4.  **File Naming**: Place the exported JSON file into the `workflows/` directory and adhere to the following naming prefixes:
    -   **Image Workflows**: Prefix must be `image_` (e.g., `image_my_style.json`)
    -   **Video Workflows**: Prefix must be `video_`
    -   **TTS Workflows**: Prefix must be `tts_`

### Common Errors and Solutions

#### 1. TTS (Text-to-Speech) Errors
-   **Reason**: The default Edge-TTS calls Microsoft's free interface, which may fail frequently due to network instability.
-   **Solution**:
    -   Check your network connection.
    -   It is recommended to switch to **ComfyUI TTS** workflows (select workflows with the `tts_` prefix) for higher stability.

#### 2. LLM (Large Language Model) Errors
-   **Troubleshooting Steps**:
    1.  Check if the **Base URL** is correct (ensure no extra spaces or incorrect suffixes).
    2.  Check if the **API Key** is valid and has sufficient balance.
    3.  Check if the **Model Name** is spelled correctly.
    -   *Tip: Please consult the official API documentation of your model provider (e.g., OpenAI, DeepSeek, Alibaba Cloud, etc.) for accurate configuration.*

#### 3. Error Message "Could not find a Chrome executable..."
-   **Reason**: Your computer system lacks the Chrome browser core, causing features dependent on the browser to fail.
-   **Solution**: Please download and install the Google Chrome browser.

### Where are generated videos saved?

All generated videos are automatically saved in the `output/` folder within the project directory. Upon completion, the interface will display the video duration, file size, number of shots, and a download link.

### Community Resources

-   **Project**: Morpheus Video Studio
-   **Issue Reporting**: Submit bugs or feature requests via GitHub Issues.
-   **Community Support**: Join discussion groups for help and experience sharing.
-   **Contribution**: The project is under the MIT license and welcomes contributions.

💡 **Tip**: If you cannot find the answer you need in this FAQ, please submit an issue on GitHub or join the community discussion. We will continue to update this FAQ based on user feedback!
