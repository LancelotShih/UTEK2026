# **Description**

Developed as part of the **UTEK 2026 Hackathon**, **VisiHelp** is a low-cost wearable device designed to help visually impaired individuals read text in their surroundings. The system captures images of text, transcribes them, and reads the text aloud using a combination of locally hosted web servers and cloud-based OCR and text-to-speech (TTS) services.

The device uses an **ESP32-CAM module** to capture images and host a local web server that communicates with a cloud backend for image processing. Once an image is captured, it is sent to **OpenAI's GPT-4.1 Mini API**, which extracts the text from the image. The transcribed text is then passed to **Google Cloud's TTS API**, which converts it into an audio file. This file is hosted on a second web server that users can access through their mobile devices. The mobile interface also allows users to control the camera, capture images, and play back the generated audio.

One of the main priorities throughout development was keeping the system **affordable, comfortable, and easy to use**. The only dedicated hardware required is the ESP32-CAM module and a custom headband, designed with inspiration from adjustable smartwatch bands to securely hold the camera in place. All image processing and audio generation are handled through software, removing the need for additional processing or audio hardware.

By keeping the hardware simple and making use of existing cloud services and mobile devices, VisiHelp provides a practical and affordable approach to making printed text more accessible to people with visual impairments.

# **Challenges**

One of the first major challenges we faced was getting the **ESP32-CAM to capture images with sufficient quality for OCR**. Since the camera uses manual focus, we needed to make sure the images contained enough detail for the text recognition software to work reliably. We eventually improved image quality by using the built-in flash LED to provide additional lighting and adjusting camera settings in software, including exposure, contrast, and resolution. Finding the right balance between image quality and file size was also important, as larger images would increase transfer times and slow down the overall system.

The flash LED introduced another issue, as leaving it on for extended periods caused it to overheat. To address this, we implemented a timer that would automatically turn off the LED after use, ensuring it was only active when needed to capture an image.

Another challenge was developing a **comfortable and affordable mounting solution**. Our initial idea was to mount the camera onto a pair of glasses, but after experimenting with different mounting positions, we found that a headband offered better stability and comfort over longer periods. We ended up designing an adjustable headband from a single 8 × 10-inch sheet of cardboard, allowing it to expand or contract to accommodate different head sizes. This kept the design simple, lightweight, and inexpensive while still providing a secure mounting point for the camera.

One of the biggest constraints was the **five-hour time limit** for the entire project. All planning, design, development, integration, and testing had to be completed within this period. With four team members working on different parts of the system simultaneously, clear communication and trust were essential. We had to divide responsibilities effectively, coordinate our progress, and make quick decisions to ensure that all components could be integrated into a working prototype before the deadline.

# **Gallery**

![Block Diagram](Visihelp_Block_Diagram.png)

![On Head](Visihelp_Wearable.jpg)

