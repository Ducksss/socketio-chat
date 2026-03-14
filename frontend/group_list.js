(function() {
const BaseUrl = "http://127.0.0.1:8000";
const FrontBaseUrl = "http://127.0.0.1";

const username = getCookie("username");
const token = getCookie("token");
if (token && username) {
  console.log(username);
} else window.location.href = FrontBaseUrl + "/login.html";

document.addEventListener("DOMContentLoaded", () => {
  const userGroupsList = document.getElementById("user-groups");

  const headers = new Headers({
    Authorization: `Bearer ${token}`,
  });
  const emojis = [
    "⭐",
    "🎉",
    "🎆",
    "💪",
    "❄️",
    "🎈",
    "❤️",
    "✨",
    "🖼️",
    "💎",
    "📞",
    "☔",
    "🍎",
    "😀",
    "🤣",
    "😎",
    "🤑",
    "😇",
    "🤡",
    "👻",
    "💩",
    "🐒",
    "🐞",
    "🦴",
    "🫅",
    "🥝",
    "🍉",
    "🌵",
    "🚗",
    "🛻",
    "🚚",
    "🚢",
    "🌏",
    "🎸",
    "🗿",
    "⌛",
    "🍕",
    "☘️",
    "🦆",
    "🏦",
    "💃",
  ];

  function addGroupToList(group) {
    const listItem = document.createElement("li");
    listItem.classList.add("group-item");
    listItem.id = "list_groups";

    // Highlight active group in double-pane view
    const activeGroupId = getCookie("group");
    if (activeGroupId && group.id && activeGroupId == group.id.toString()) {
      listItem.classList.add("active");
    }

    // Avatar
    const avatar = document.createElement("div");
    avatar.classList.add("group-avatar");
    if (group.notfound) {
      avatar.classList.add("empty");
      avatar.textContent = "!";
    } else {
      // Use initials or a random color for avatar in a real app.
      // We'll just put the first letter of the name or a default icon.
      avatar.textContent = group.name ? group.name.charAt(0).toUpperCase() : "#";
    }
    
    // Info Container
    const groupInfo = document.createElement("div");
    groupInfo.classList.add("group-info");

    const headerRow = document.createElement("div");
    headerRow.classList.add("group-header");

    const groupName = document.createElement("div");
    groupName.classList.add("group-name");
    groupName.textContent = group.name;

    const groupTime = document.createElement("div");
    groupTime.classList.add("group-time");
    // Just a placeholder for the WA "last message time" look
    // We could put last message time if API supported it, substituting a static string or leaving blank.
    if (!group.notfound) {
      // randomly generated time string or just nothing
      // groupTime.textContent = "12:00 PM"; 
    }

    headerRow.appendChild(groupName);
    headerRow.appendChild(groupTime);

    groupInfo.appendChild(headerRow);

    if (!group.notfound) {
      const groupAddress = document.createElement("div");
      groupAddress.classList.add("group-address");
      groupAddress.textContent = "@" + group.address;
      groupInfo.appendChild(groupAddress);
    }

    listItem.appendChild(avatar);
    listItem.appendChild(groupInfo);

    listItem.addEventListener("click", () => {
      setCookie("group", group.id, 1);
      setCookie("group_name", group.name, 1);
      window.location.href = FrontBaseUrl + "/chat.html";
    });

    if (userGroupsList) {
      userGroupsList.appendChild(listItem);
    }
  }

  // Your existing fetch code to get user groups remains the same
  fetch(BaseUrl + "/user/groups", { headers })
    .then((response) => response.json())
    .then((data) => {
      if (data.groups === undefined || data.groups.length == 0) {
        (noGroup = {
          id: "",
          name: "You aren't a member of any group😴",
          address: "",
          notfound: true,
        }),
          addGroupToList(noGroup);
      }
      data.groups.forEach((group) => {
        addGroupToList(group);
      });
    })
    .catch((error) => console.error("Error:", error));
});

function setCookie(cname, cvalue, exdays) {
  const d = new Date();
  d.setTime(d.getTime() + exdays * 24 * 60 * 60 * 1000);
  let expires = "expires=" + d.toUTCString();
  document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}
function getCookie(cname) {
  let name = cname + "=";
  let decodedCookie = decodeURIComponent(document.cookie);
  let ca = decodedCookie.split(";");
  for (let i = 0; i < ca.length; i++) {
    let c = ca[i];
    while (c.charAt(0) == " ") {
      c = c.substring(1);
    }
    if (c.indexOf(name) == 0) {
      return c.substring(name.length, c.length);
    }
  }
  return "";
}

function joinGroup(username) {
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
  });
  fetch(BaseUrl + `/group/join?address=${username}`, {
    method: "POST",
    headers: headers,
  })
    .then((response) => {
      if (response.status == "404") {
        alert(
          "This group is not available. Please be careful in entering the username."
        );
      } else response.json();
    })
    .then((data) => {
      console.log(data);
      window.location.reload();
    })
    .catch((error) =>
      alert(
        "This group is not available. Please be careful in entering the username."
      )
    );
}

function createGroup(username, name) {
  console.log(username, name);
  const headers = new Headers({
    Authorization: `Bearer ${token}`,
  });
  fetch(BaseUrl + `/group/create/?address=${username}&name=${name}`, {
    method: "POST",
    headers: headers,
  })
    .then((response) => {
      if (response.status == "400") {
        alert("This username already exists");
      } else response.json();
    })
    .then((data) => {
      console.log(data);
      window.location.reload();
    })
    .catch((error) => alert("There is a problem creating the group"));
}
const joinButton = document.getElementById("joinButton");
if (joinButton) {
  joinButton.addEventListener("click", function () {
    var username = document.getElementById("username").value;
    joinGroup(username);
  });
}

const create_group_btn = document.getElementById("create_group_btn");
if (create_group_btn) {
  create_group_btn.addEventListener("click", function () {
    var username = document.getElementById("create_username").value;
    var groupname = document.getElementById("create_groupname").value;
    createGroup(username, groupname);
  });
}
window.handleLogoutClick = function() {
  document.cookie = "username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
  document.cookie = "token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
  document.cookie = "group=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
  document.cookie =
    "group_name=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";

  console.log("User clicked LogOut");
  window.location.href = FrontBaseUrl + "/login.html";
};
const headersGlobal = new Headers({
  Authorization: `Bearer ${token}`,
});
fetch(BaseUrl + "/user/me", { headers: headersGlobal }).then((response) => {
  if (response.status != "200") {
    window.handleLogoutClick();
  }
});

})();
