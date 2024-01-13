
## bug
### 用户增加时区
### 需要控制同一账号多处登录
### 不可以连续收听音频

## `streamlit`

### 需要重启 cloud

- 私密设置更新时
- `Home`及`pages/`之外的代码修改后

### tabs

- 同一页内所有tab都会运行，有必要设置子菜单（下拉框）分离

### caching
`session_state`会话状态只针对单个用户，对于其他用户是不可见的；而缓存针对所有用户，是共享的；`cache_data`返回是副本；`cache_resource`返回对象本身。
#### session_state
#### cache_data
#### cache_resource

### 代码更新

除`Home`和`pages/`下的代码能立即更新外，其他处与app相关的代码修改后，需要重启动app。

## firestore

### tip
- 以特定的属性命名文档不是好主意。例如以用户手机号码命名用户文档，容易造成不易察觉的删除