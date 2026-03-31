let currentPage = 1;

function loadUsers() {

    let search = document.getElementById("searchBox").value;

    fetch(`/admin/api/users?page=${currentPage}&search=${search}`)
    .then(res => res.json())
    .then(data => {

        let tbody = document.querySelector("#usersTable tbody");

        tbody.innerHTML = "";

        data.users.forEach(user => {

            let row = `
            <tr>

            <td>${user.id}</td>

            <td>${user.username}</td>

            <td>${user.email}</td>

            <td>${user.sponsor_id}</td>

            <td>${user.wallet}</td>

            <td>${user.created_at}</td>

            <td>

            <button class="btn btn-sm btn-info"
            onclick="viewUser(${user.id})">
            View
            </button>

            <button class="btn btn-sm btn-warning">
            Wallet
            </button>

            <button class="btn btn-sm btn-danger">
            Block
            </button>

            </td>

            </tr>
            `;

            tbody.innerHTML += row;

        });

        document.getElementById("pageInfo").innerText =
        `Page ${data.page} of ${data.pages}`;

    });

}


document.getElementById("searchBox")
.addEventListener("keyup", function(){

currentPage = 1;

loadUsers();

});


document.getElementById("nextPage")
.addEventListener("click", function(){

currentPage++;

loadUsers();

});


document.getElementById("prevPage")
.addEventListener("click", function(){

if(currentPage > 1){

currentPage--;

loadUsers();

}

});


function viewUser(id){

window.location.href = `/admin/user/${id}`;

}


loadUsers();
