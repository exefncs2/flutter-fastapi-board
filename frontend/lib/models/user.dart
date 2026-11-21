// lib/models/user.dart

/// 使用者模型類，用於表示登入使用者的資訊
class User {
  final String username;
  final String token;

  /// 構造函式，初始化使用者屬性
  User({
    required this.username,
    required this.token,
  });

  /// 從 JSON 建立 User 物件的工廠方法
  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      username: json['username'],
      token: json['token'],
    );
  }

  /// 將 User 物件轉換為 JSON 的方法
  Map<String, dynamic> toJson() {
    return {
      'username': username,
      'token': token,
    };
  }
}