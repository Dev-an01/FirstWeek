// backend/chat-service/test-websocket-comprehensive.js
// Comprehensive WebSocket test script covering all features

const io = require("socket.io-client");
const axios = require("axios");

// Use service names for Docker internal network
const AUTH_URL = "http://auth-service:3001/api/users";
const CHAT_URL = "http://localhost:3002/api/chat";
const WEBSOCKET_URL = "http://localhost:3002";

let accessToken = null;
let conversationId = null;

// Test user credentials
const testUser = {
  identifier: "executive3@test.com",
  password: "TestPass123!",
};

// Full test user data for registration
const testUserRegistration = {
  username: "executive3",
  email: "executive3@test.com",
  password: "TestPass123!",
  firstName: "Test",
  lastName: "Executive",
};

/**
 * Register test user
 */
async function registerUser() {
  console.log("\n=== User Registration ===");
  try {
    const response = await axios.post(
      `${AUTH_URL}/register`,
      testUserRegistration,
      {
        withCredentials: true,
      },
    );

    console.log("✓ User registered successfully");
    console.log(`  Username: ${response.data.data.user.username}`);
    console.log(`  Email: ${response.data.data.user.email}`);
    console.log(`  Role: ${response.data.data.user.role}`);
    return true;
  } catch (error) {
    if (
      error.response?.status === 409 ||
      error.response?.data?.error?.code === "USER_EXISTS"
    ) {
      console.log("ℹ User already exists (this is OK)");
      return true;
    }
    console.log(
      "✗ Registration failed:",
      error.response?.data?.error?.message || error.message,
    );
    return false;
  }
}

/**
 * Login and get access token
 */
async function login() {
  console.log("\n=== Step 1: Login ===");
  try {
    const response = await axios.post(`${AUTH_URL}/login`, testUser, {
      withCredentials: true,
    });

    const cookies = response.headers["set-cookie"];
    if (cookies) {
      const tokenCookie = cookies.find((c) =>
        c.startsWith("firstweek_avatar_access_token="),
      );
      if (tokenCookie) {
        accessToken = tokenCookie.split(";")[0].split("=")[1];
        console.log("✓ Login successful");
        console.log("✓ Access token obtained");
        return true;
      }
    }

    console.log("✗ Failed to extract access token");
    return false;
  } catch (error) {
    // Check if error is "Invalid credentials" or authentication error
    const isAuthError =
      error.response?.status === 401 ||
      error.response?.status === 404 ||
      error.response?.status === 500;
    const isInvalidCredentials =
      error.response?.data?.error?.code === "AUTHENTICATION_ERROR" ||
      error.response?.data?.error?.message?.includes("Invalid credentials");

    // If login fails due to invalid credentials, try to register
    if (isAuthError && isInvalidCredentials) {
      console.log("ℹ User doesn't exist, attempting registration...");

      const registrationSuccess = await registerUser();
      if (!registrationSuccess) {
        console.log("✗ Login failed: Could not register user");
        return false;
      }

      // Try login again after registration
      console.log("\n=== Retrying Login After Registration ===");
      try {
        const retryResponse = await axios.post(`${AUTH_URL}/login`, testUser, {
          withCredentials: true,
        });

        const cookies = retryResponse.headers["set-cookie"];
        if (cookies) {
          const tokenCookie = cookies.find((c) =>
            c.startsWith("firstweek_avatar_access_token="),
          );
          if (tokenCookie) {
            accessToken = tokenCookie.split(";")[0].split("=")[1];
            console.log("✓ Login successful after registration");
            console.log("✓ Access token obtained");
            return true;
          }
        }
      } catch (retryError) {
        console.log(
          "✗ Login failed after registration:",
          retryError.response?.data?.error?.message || retryError.message,
        );
        return false;
      }
    }

    console.log(
      "✗ Login failed:",
      error.response?.data?.error?.message || error.message,
    );
    return false;
  }
}

/**
 * Create a test conversation
 */
async function createConversation() {
  console.log("\n=== Step 2: Create Conversation ===");
  try {
    const response = await axios.post(
      `${CHAT_URL}/conversations`,
      { title: "WebSocket Comprehensive Test" },
      {
        headers: {
          Cookie: `firstweek_avatar_access_token=${accessToken}`,
        },
      },
    );

    conversationId = response.data.data.id;
    console.log("✓ Conversation created");
    console.log(`✓ Conversation ID: ${conversationId}`);
    return true;
  } catch (error) {
    console.log("✗ Failed to create conversation:", error.message);
    return false;
  }
}

/**
 * Set user preferences for testing
 */
async function setPreferences() {
  console.log("\n=== Step 3: Set User Preferences ===");
  try {
    const response = await axios.patch(
      `${CHAT_URL}/preferences`,
      {
        defaultProfileId: "exec_002_test",
        defaultTopK: 8,
        defaultMinScore: 0.75,
      },
      {
        headers: {
          Cookie: `firstweek_avatar_access_token=${accessToken}`,
        },
      },
    );

    console.log("✓ Preferences set");
    console.log(
      `  Profile: ${response.data.data.preferences.defaultProfileId}`,
    );
    console.log(`  TopK: ${response.data.data.preferences.defaultTopK}`);
    console.log(
      `  MinScore: ${response.data.data.preferences.defaultMinScore}`,
    );
    return true;
  } catch (error) {
    console.log("✗ Failed to set preferences:", error.message);
    return false;
  }
}

/**
 * Test 1: Connection with auth object (recommended method)
 */
function testAuthObjectConnection() {
  return new Promise((resolve, reject) => {
    console.log("\n=== Test 1: Auth Object Connection ===");

    const socket = io(WEBSOCKET_URL, {
      auth: {
        token: accessToken,
      },
      transports: ["websocket"],
    });

    socket.on("connect", () => {
      console.log("✓ Connected with auth object");
      socket.disconnect();
      resolve(socket);
    });

    socket.on("connect_error", (error) => {
      console.log("✗ Auth object connection failed:", error.message);
      reject(error);
    });

    setTimeout(() => reject(new Error("Timeout")), 5000);
  });
}

/**
 * Test 2: Connection with query parameter
 */
function testQueryParamConnection() {
  return new Promise((resolve, reject) => {
    console.log("\n=== Test 2: Query Parameter Connection ===");

    const socket = io(`${WEBSOCKET_URL}?token=${accessToken}`, {
      transports: ["websocket"],
    });

    socket.on("connect", () => {
      console.log("✓ Connected with query parameter");
      socket.disconnect();
      resolve(socket);
    });

    socket.on("connect_error", (error) => {
      console.log("✗ Query param connection failed:", error.message);
      reject(error);
    });

    setTimeout(() => reject(new Error("Timeout")), 5000);
  });
}

/**
 * Main WebSocket tests
 */
function testWebSocketFeatures() {
  return new Promise((resolve, reject) => {
    console.log("\n=== Test 3: WebSocket Features ===");

    const socket = io(WEBSOCKET_URL, {
      auth: { token: accessToken },
      transports: ["websocket"],
    });

    const testResults = {
      connection: false,
      welcomeMessage: false,
      joinRoom: false,
      ping: false,
      typing: false,
      onlineUsers: false,
      messageWithoutRagOptions: false,
      messageWithRagOptions: false,
      streaming: false,
      leaveRoom: false,
    };

    // Connection
    socket.on("connect", () => {
      console.log("\n✓ WebSocket connected");
      console.log(`  Socket ID: ${socket.id}`);
      testResults.connection = true;
    });

    // Welcome message
    socket.on("connected", (data) => {
      console.log("✓ Received welcome message");
      console.log(
        `  User: ${data.data.user.username} (${data.data.user.role})`,
      );
      testResults.welcomeMessage = true;

      // Test ping/pong
      console.log("\n--- Testing Ping/Pong ---");
      socket.emit("ping");
    });

    // Ping/Pong
    socket.on("pong", (data) => {
      console.log("✓ Ping/Pong working");
      console.log(`  Timestamp: ${data.timestamp}`);
      testResults.ping = true;

      // Join conversation
      console.log("\n--- Testing Join Conversation ---");
      socket.emit("chat:join", { conversationId }, (response) => {
        if (response.success) {
          console.log("✓ Joined conversation room");
          console.log(`  Conversation: ${response.data.conversation.title}`);
          testResults.joinRoom = true;

          // Test typing indicator
          console.log("\n--- Testing Typing Indicator ---");
          socket.emit("chat:typing", {
            conversationId,
            isTyping: true,
          });

          setTimeout(() => {
            socket.emit("chat:typing", {
              conversationId,
              isTyping: false,
            });
            testResults.typing = true;
            console.log("✓ Typing indicators sent");

            // Test get online users
            console.log("\n--- Testing Get Online Users ---");
            socket.emit(
              "chat:get-online-users",
              { conversationId },

              (response2) => {
                if (response2.success) {
                  console.log("✓ Online users retrieved");
                  console.log(`  Count: ${response2.data.count}`);
                  console.log(
                    `  Users: ${response2.data.onlineUsers.map((u) => u.username).join(", ")}`,
                  );
                  testResults.onlineUsers = true;

                  // Test message without ragOptions (should use preferences)
                  console.log("\n--- Testing Message WITHOUT ragOptions ---");
                  console.log(
                    "  (Should use preferences: exec_002_test, topK=8, minScore=0.75)",
                  );

                  socket.emit(
                    "chat:message",
                    {
                      conversationId,
                      content: "What is the the remote work policy?",
                      // NO ragOptions - should use user preferences
                    },
                    (msgResponse) => {
                      if (msgResponse.success) {
                        console.log("✓ Message sent without ragOptions");
                        console.log(
                          `  User message ID: ${msgResponse.data.userMessage.id}`,
                        );
                        console.log(
                          `  Processing time: ${msgResponse.data.processingTime}ms`,
                        );
                        testResults.messageWithoutRagOptions = true;
                      } else {
                        console.log(
                          "✗ Message without ragOptions failed:",
                          msgResponse.error.message,
                        );
                      }
                    },
                  );
                } else {
                  console.log(
                    "✗ Get online users failed:",
                    response2.error.message,
                  );
                }
              },
            );
          }, 500);
        } else {
          console.log("✗ Join conversation failed:", response.error.message);
        }
      });
    });

    // Listen for user:joined event
    socket.on("user:joined", (data) => {
      console.log(`  User joined: ${data.username}`);
    });

    // Listen for user:left event
    socket.on("user:left", (data) => {
      console.log(`  User left: ${data.username}`);
    });

    // Listen for typing events
    socket.on("user:typing", (data) => {
      console.log(
        `  ${data.username} is ${data.isTyping ? "typing" : "stopped typing"}`,
      );
    });

    // Listen for user message
    // eslint-disable-next-line no-unused-vars
    socket.on("message:user", (data) => {
      console.log("  → User message broadcast received");
    });

    // Listen for streaming
    // eslint-disable-next-line no-unused-vars
    let streamBuffer = "";
    let isStreaming = false;
    let messageCount = 0;

    socket.on("message:stream", (data) => {
      if (!isStreaming) {
        console.log("  → Streaming started...");
        process.stdout.write("    ");
        isStreaming = true;
      }
      process.stdout.write(data.chunk);
      streamBuffer = data.accumulated;
    });

    // Listen for complete message
    socket.on("message:complete", (data) => {
      if (isStreaming) {
        console.log("\n  → Streaming completed");
        console.log(`    Processing time: ${data.processingTime}ms`);
        isStreaming = false;
        streamBuffer = "";
        messageCount++;

        testResults.streaming = true;

        // After first message, send second message WITH ragOptions
        if (messageCount === 1) {
          console.log("\n--- Testing Message WITH ragOptions ---");
          console.log(
            "  (Should override preferences with exec_004_test, topK=3)",
          );

          socket.emit(
            "chat:message",
            {
              conversationId,
              content: "What are the company's policy about the remote work?",
              ragOptions: {
                profileId: "exec_004_test",
                topK: 3,
                minScore: 0.8,
              },
            },
            (msgResponse) => {
              if (msgResponse.success) {
                console.log("✓ Message sent with ragOptions");
                console.log(
                  `  User message ID: ${msgResponse.data.userMessage.id}`,
                );
                console.log(
                  `  Processing time: ${msgResponse.data.processingTime}ms`,
                );
                testResults.messageWithRagOptions = true;
              } else {
                console.log(
                  "✗ Message with ragOptions failed:",
                  msgResponse.error.message,
                );
              }
            },
          );
        }

        // After second message, test leave room
        if (messageCount === 2) {
          console.log("\n--- Testing Leave Conversation ---");
          socket.emit("chat:leave", { conversationId }, (response) => {
            if (response.success) {
              console.log("✓ Left conversation room");
              testResults.leaveRoom = true;

              // All tests complete
              setTimeout(() => {
                console.log("\n=== Test Results ===");
                const passed =
                  Object.values(testResults).filter(Boolean).length;
                const total = Object.keys(testResults).length;

                Object.entries(testResults).forEach(([test, result]) => {
                  console.log(`  ${result ? "✓" : "✗"} ${test}`);
                });

                console.log(`\nTests passed: ${passed}/${total}`);
                socket.disconnect();

                if (passed === total) {
                  resolve(testResults);
                } else {
                  reject(new Error(`Only ${passed}/${total} tests passed`));
                }
              }, 1000);
            } else {
              console.log(
                "✗ Leave conversation failed:",
                response.error.message,
              );
            }
          });
        }
      }
    });

    // Error handlers
    socket.on("connect_error", (error) => {
      console.log("✗ Connection error:", error.message);
      reject(error);
    });

    socket.on("error", (error) => {
      console.log("✗ Socket error:", error);
      reject(error);
    });

    // Timeout
    setTimeout(() => {
      console.log("\n✗ Test timeout");
      socket.disconnect();
      reject(new Error("Test timeout"));
    }, 90000);
  });
}

/**
 * Verify preferences were used correctly
 */
async function verifyPreferencesUsage() {
  console.log("\n=== Step 4: Verify Preferences Usage ===");

  // This would require checking logs or database
  // For now, just inform the user to check logs manually
  console.log("ℹ Check chat-service logs for RAG API calls:");
  console.log("  docker compose logs chat-service --since 5m | grep profileId");
  console.log("");
  console.log("Expected:");
  console.log(
    '  1st message (no ragOptions): profileId="exec_002_test", topK=8, minScore=0.75',
  );
  console.log(
    '  2nd message (with ragOptions): profileId="exec_004_test", topK=3, minScore=0.8',
  );

  return true;
}

/**
 * Run all tests
 */
async function runTests() {
  console.log("╔══════════════════════════════════════════════════╗");
  console.log("║  Comprehensive WebSocket Test Suite             ║");
  console.log("╚══════════════════════════════════════════════════╝");

  try {
    // Step 1: Login
    const loginSuccess = await login();
    if (!loginSuccess) {
      console.log("\n✗ Test suite failed: Login unsuccessful");
      process.exit(1);
    }

    // Step 2: Create conversation
    const convSuccess = await createConversation();
    if (!convSuccess) {
      console.log("\n✗ Test suite failed: Conversation creation unsuccessful");
      process.exit(1);
    }

    // Step 3: Set preferences
    const prefsSuccess = await setPreferences();
    if (!prefsSuccess) {
      console.log("\n✗ Test suite failed: Preferences setup unsuccessful");
      process.exit(1);
    }

    // Test 1: Auth object connection
    await testAuthObjectConnection();

    // Test 2: Query param connection
    await testQueryParamConnection();

    // Test 3: All WebSocket features
    await testWebSocketFeatures();

    // Step 4: Verify preferences
    await verifyPreferencesUsage();

    console.log("\n╔══════════════════════════════════════════════════╗");
    console.log("║  ✓ All WebSocket Tests Completed Successfully   ║");
    console.log("╚══════════════════════════════════════════════════╝\n");
    process.exit(0);
  } catch (error) {
    console.log("\n╔══════════════════════════════════════════════════╗");
    console.log("║  ✗ WebSocket Test Suite Failed                   ║");
    console.log("╚══════════════════════════════════════════════════╝");
    console.log("\nError:", error.message);
    process.exit(1);
  }
}

// Run tests
runTests();
