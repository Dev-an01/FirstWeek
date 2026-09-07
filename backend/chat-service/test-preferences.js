// backend/chat-service/test-preferences.js
// Test script for user preferences endpoints

const axios = require("axios");

const AUTH_URL = "http://auth-service:3001/api/users";
const CHAT_URL = "http://localhost:3002/api/chat";

let accessToken = null;

// Test user credentials
const testUser = {
  identifier: "executive3@test.com",
  password: "TestPass123!",
};

/**
 * Login and get access token
 */
async function login() {
  console.log("\n=== Step 1: Login ===");
  try {
    const response = await axios.post(`${AUTH_URL}/login`, testUser, {
      withCredentials: true,
    });

    // Extract token from Set-Cookie header
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
    console.log("✗ Login failed:", error.message);
    return false;
  }
}

/**
 * Test get preferences
 */
async function testGetPreferences() {
  console.log("\n=== Step 2: Get User Preferences ===");
  try {
    const response = await axios.get(`${CHAT_URL}/preferences`, {
      headers: {
        Cookie: `firstweek_avatar_access_token=${accessToken}`,
      },
    });

    console.log("✓ Preferences retrieved successfully");
    console.log(
      "  Preferences:",
      JSON.stringify(response.data.data.preferences, null, 2),
    );
    return response.data.data.preferences;
  } catch (error) {
    console.log(
      "✗ Failed to get preferences:",
      error.response?.data || error.message,
    );
    return null;
  }
}

/**
 * Test update preferences
 */
async function testUpdatePreferences() {
  console.log("\n=== Step 3: Update User Preferences ===");
  try {
    const updates = {
      defaultProfileId: "exec_001_test", // Change to exec_001_test
      defaultTopK: 10,
      defaultMinScore: 0.7,
      theme: "dark",
    };

    console.log("  Updating with:", JSON.stringify(updates, null, 2));

    const response = await axios.patch(`${CHAT_URL}/preferences`, updates, {
      headers: {
        Cookie: `firstweek_avatar_access_token=${accessToken}`,
      },
    });

    console.log("✓ Preferences updated successfully");
    console.log(
      "  Updated preferences:",
      JSON.stringify(response.data.data.preferences, null, 2),
    );
    return response.data.data.preferences;
  } catch (error) {
    console.log(
      "✗ Failed to update preferences:",
      error.response?.data || error.message,
    );
    return null;
  }
}

/**
 * Test reset preferences
 */
async function testResetPreferences() {
  console.log("\n=== Step 4: Reset Preferences to Defaults ===");
  try {
    const response = await axios.post(
      `${CHAT_URL}/preferences/reset`,
      {},
      {
        headers: {
          Cookie: `firstweek_avatar_access_token=${accessToken}`,
        },
      },
    );

    console.log("✓ Preferences reset successfully");
    console.log(
      "  Reset preferences:",
      JSON.stringify(response.data.data.preferences, null, 2),
    );
    return response.data.data.preferences;
  } catch (error) {
    console.log(
      "✗ Failed to reset preferences:",
      error.response?.data || error.message,
    );
    return null;
  }
}

/**
 * Verify preferences are used in messaging
 */
async function testPreferencesInMessaging() {
  console.log("\n=== Step 5: Verify Preferences Used in Messaging ===");

  // First, set preferences to exec_001_test
  console.log("  Setting profile to exec_001_test...");
  try {
    await axios.patch(
      `${CHAT_URL}/preferences`,
      { defaultProfileId: "exec_001_test" },
      {
        headers: { Cookie: `firstweek_avatar_access_token=${accessToken}` },
      },
    );
    console.log("✓ Profile set to exec_001_test");
  } catch (error) {
    console.log("✗ Failed to set profile");
    return false;
  }

  // Create a test conversation
  console.log("  Creating test conversation...");
  let conversationId;
  try {
    const response = await axios.post(
      `${CHAT_URL}/conversations`,
      { title: "Preferences Test Conversation" },
      {
        headers: { Cookie: `firstweek_avatar_access_token=${accessToken}` },
      },
    );
    conversationId = response.data.data.id;
    console.log("✓ Conversation created:", conversationId);
  } catch (error) {
    console.log("✗ Failed to create conversation");
    return false;
  }

  // Send a message (should use exec_001_test profile from preferences)
  console.log("  Sending message (should use exec_001_test profile)...");
  try {
    const response = await axios.post(
      `${CHAT_URL}/conversations/${conversationId}/messages`,
      {
        content: "What is the company's vacation policy?",
        // NOTE: Not providing ragOptions.profileId - should use preferences
      },
      {
        headers: { Cookie: `firstweek_avatar_access_token=${accessToken}` },
      },
    );

    console.log("✓ Message sent successfully");
    console.log(
      "  Assistant response length:",
      response.data.data.assistantMessage.content.length,
    );
    console.log(
      "  First 200 chars:",
      `${response.data.data.assistantMessage.content.substring(0, 200)}...`,
    );

    return true;
  } catch (error) {
    console.log(
      "✗ Failed to send message:",
      error.response?.data || error.message,
    );
    return false;
  }
}

/**
 * Run all tests
 */
async function runTests() {
  console.log("╔══════════════════════════════════════════╗");
  console.log("║  User Preferences Test Suite            ║");
  console.log("╚══════════════════════════════════════════╝");

  try {
    // Step 1: Login
    const loginSuccess = await login();
    if (!loginSuccess) {
      console.log("\n✗ Test suite failed: Login unsuccessful");
      process.exit(1);
    }

    // Step 2: Get preferences
    const prefs1 = await testGetPreferences();
    if (!prefs1) {
      console.log("\n✗ Test suite failed: Could not get preferences");
      process.exit(1);
    }

    // Step 3: Update preferences
    const prefs2 = await testUpdatePreferences();
    if (!prefs2) {
      console.log("\n✗ Test suite failed: Could not update preferences");
      process.exit(1);
    }

    // Verify updates
    if (
      prefs2.defaultProfileId !== "exec_001_test" ||
      prefs2.defaultTopK !== 10
    ) {
      console.log("\n✗ Test suite failed: Preferences not updated correctly");
      process.exit(1);
    }

    // Step 4: Reset preferences
    const prefs3 = await testResetPreferences();
    if (!prefs3) {
      console.log("\n✗ Test suite failed: Could not reset preferences");
      process.exit(1);
    }

    // Verify reset
    if (
      prefs3.defaultProfileId !== "exec_003_test" ||
      prefs3.defaultTopK !== 5
    ) {
      console.log("\n✗ Test suite failed: Preferences not reset correctly");
      process.exit(1);
    }

    // Step 5: Test preferences in messaging
    const messagingSuccess = await testPreferencesInMessaging();
    if (!messagingSuccess) {
      console.log("\n✗ Test suite failed: Preferences not used in messaging");
      process.exit(1);
    }

    console.log("\n╔══════════════════════════════════════════╗");
    console.log("║  ✓ All Tests Passed!                    ║");
    console.log("╚══════════════════════════════════════════╝\n");
    process.exit(0);
  } catch (error) {
    console.log("\n╔══════════════════════════════════════════╗");
    console.log("║  ✗ Test Suite Failed                    ║");
    console.log("╚══════════════════════════════════════════╝");
    console.log("\nError:", error.message);
    process.exit(1);
  }
}

// Run tests
runTests();
