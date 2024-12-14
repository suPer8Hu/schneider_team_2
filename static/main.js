import { GoogleGenerativeAI } from "@google/generative-ai";

const businessInfo = `

General Business Information:
Website: www.schneiderfreightpower.com

Support Email: support@schneiderfreightpower.com

Customer Service: Available 24/7 via phone and email.

Green Bay Location:
Address: 3101 S Packerland Dr, Green Bay, WI 54313, USA
Phone: +1 920-592-2000
Email: greenbay@schneiderfreightpower.com
Opening Hours:
Monday to Friday: 8:00 AM to 5:00 PM
Saturday: 9:00 AM to 1:00 PM
Sunday: Closed

Return Policy:
Service Refunds: Refunds are available for bookings canceled at least 24 hours before the scheduled freight departure time.
Claims for Issues: Contact customer support for any issues related to delayed, damaged, or lost freight.

FAQs:
General:
What services does Schneider FreightPower offer?
Schneider FreightPower provides freight booking, tracking, and management services for Dry Van, Reefer, Flatbed, and Power-Only freight options.

How can I contact customer support?
You can email us at support@schneiderfreightpower.com or call our Green Bay office at +1 920-592-2000.

How do I track my shipment?
Real-time tracking is available via the FreightPower app. Simply log in and access your active bookings.

What is the cancellation policy?
Cancellations made at least 24 hours before the scheduled departure are eligible for a full refund.

What are the supported load weights?
Standard load weights vary, with a maximum of 45,000 lbs for Dry Van bookings.

Booking & Operations:
How can I book a load?
Use the FreightPower app or contact us at greenbay@schneiderfreightpower.com.

Can I make same-day bookings?
Same-day bookings depend on availability. Please contact our Green Bay office for urgent requests.

What areas does Schneider FreightPower cover?
We operate in the United States, Canada, and Mexico.

What happens if my shipment is delayed?
Contact our support team for assistance. We'll provide updates and help resolve any issues.

Do you provide international shipping?
Yes, Schneider FreightPower supports cross-border freight services between the US, Canada, and Mexico.

Instructions for the Tone:
Conciseness:
Responses should be short, direct, and easy to understand. Avoid long explanations unless requested.

Example:

Customer Inquiry: "How do I book a load?"
Response: "Use the FreightPower app or email us at greenbay@schneiderfreightpower.com."
Slight Formality:
Use polite and professional language while maintaining approachability. Avoid overly casual expressions.

Example:

"Thank you for reaching out! We're happy to assist."
"Please let us know if there's anything else you need."
Clarity:
Avoid jargon unless it's industry-standard and well-understood by the target audience. Always provide clarity.

Example:

Instead of: "All shipments are GPS-enabled via app interface."
Use: "Track shipments in real time using the FreightPower app."
Positive Tone:
Use a friendly and helpful tone that reassures users. Avoid negativity or ambiguity.

Example:

"Yes, we can help you with that!"
"We’re here to make your booking process seamless."
Consistency:
Ensure responses follow the same tone and style across all queries to create a cohesive user experience.

Example:

All greetings start with: "Thank you for reaching out!"
All instructions start with: "Please..."


`;


let genAI = null;
let model = null;
let messages = {
    history: [],
}

async function initializeChatbot() {
    try {
        
        const response = await fetch('/get-api-key');
        const data = await response.json();

        if (!data.key) {
            throw new Error("API Key not found in response.");
        }

        const API_KEY = data.key;

        
        genAI = new GoogleGenerativeAI(API_KEY);
        model = genAI.getGenerativeModel({
            model: "gemini-1.5-pro",
            systemInstruction: businessInfo,
        });

        console.log("Chatbot initialized successfully!");
    } catch (error) {
        console.error("Error initializing chatbot:", error);
    }
}

async function sendMessage() {

    console.log(messages);
    const userMessage = document.querySelector(".chat-window input").value;
    
    if (userMessage.length) {

        try {
            document.querySelector(".chat-window input").value = "";
            document.querySelector(".chat-window .chat").insertAdjacentHTML("beforeend",`
                <div class="user">
                    <p>${userMessage}</p>
                </div>
            `);

            document.querySelector(".chat-window .chat").insertAdjacentHTML("beforeend",`
                <div class="loader"></div>
            `);

            const chat = model.startChat(messages);

            let result = await chat.sendMessageStream(userMessage);
            
            document.querySelector(".chat-window .chat").insertAdjacentHTML("beforeend",`
                <div class="model">
                    <p></p>
                </div>
            `);
            
            let modelMessages = '';

            for await (const chunk of result.stream) {
              const chunkText = chunk.text();
              modelMessages = document.querySelectorAll(".chat-window .chat div.model");
              modelMessages[modelMessages.length - 1].querySelector("p").insertAdjacentHTML("beforeend",`
                ${chunkText}
            `);
            }

            messages.history.push({
                role: "user",
                parts: [{ text: userMessage }],
            });

            messages.history.push({
                role: "model",
                parts: [{ text: modelMessages[modelMessages.length - 1].querySelector("p").innerHTML }],
            });

        } catch (error) {
            document.querySelector(".chat-window .chat").insertAdjacentHTML("beforeend",`
                <div class="error">
                    <p>The message could not be sent. Please try again.</p>
                </div>
            `);
        }

        document.querySelector(".chat-window .chat .loader").remove();
        
    }
}

document.querySelector(".chat-window .input-area button")
.addEventListener("click", ()=>sendMessage());

document.querySelector(".chat-button")
.addEventListener("click", ()=>{
    document.querySelector("body").classList.add("chat-open");
});

document.querySelector(".chat-window button.close")
.addEventListener("click", ()=>{
    document.querySelector("body").classList.remove("chat-open");
});


initializeChatbot();