// lib/services/api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/user.dart';
import '../models/post.dart';

/// API 服務類，負責與後端伺服器通信
class ApiService {
  // 伺服器 URL，初始化為空，需要在運行時設置
  String baseUrl = '';
  // 存儲身份驗證令牌
  String? token;

  /// 構造函式，可以設置初始 URL
  ApiService({String? initialUrl}) {
    if (initialUrl != null) {
      baseUrl = initialUrl;
    }
  }

  /// 更新基礎 URL
  void updateBaseUrl(String url) {
    baseUrl = url;
    print('API URL 已更新為: $url');
  }

  /// 設置認證令牌
  void setToken(String authToken) {
    token = authToken;
    print('令牌已設置');
  }

  /// 清除認證令牌
  void clearToken() {
    token = null;
    print('令牌已清除');
  }

  /// 使用掃描的 QR 碼會話 ID 進行登入
  /// 
  /// 將掃描到的會話 ID 發送到伺服器以完成登入過程
  Future<User> loginWithQrSession(String sessionId) async {
    if (baseUrl.isEmpty) {
      throw Exception('伺服器 URL 未設置');
    }
    
    print('發送登入請求到 $baseUrl/api/qr-login');
    final response = await http.post(
      Uri.parse('$baseUrl/api/qr-login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'session_id': sessionId}),
    );
    
    print('收到回應，狀態碼: ${response.statusCode}');
    if (response.statusCode == 200) {
      final userData = jsonDecode(utf8.decode(response.bodyBytes));
      // 保存令牌以供後續請求使用
      if (userData['token'] != null) {
        token = userData['token'];
        print('已保存登入令牌');
      }
      return User.fromJson(userData);
    } else {
      print('登入失敗: ${response.body}');
      throw Exception('登入失敗: ${response.body}');
    }
  }

  /// 取得當前登入使用者的資訊
  Future<User> getUserInfo() async {
    _checkTokenAndUrl();
    
    final response = await http.get(
      Uri.parse('$baseUrl/api/users/me'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );
    
    if (response.statusCode == 200) {
      return User.fromJson(jsonDecode(utf8.decode(response.bodyBytes)));
    } else {
      throw Exception('取得使用者資訊失敗: ${response.body}');
    }
  }

  /// 取得所有貼文
  Future<List<Post>> getPosts() async {
    _checkTokenAndUrl();
    
    print('取得貼文列表');
    final response = await http.get(
      Uri.parse('$baseUrl/api/posts'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );
    
    if (response.statusCode == 200) {
      print('成功取得貼文列表');
      List<dynamic> jsonResponse = jsonDecode(utf8.decode(response.bodyBytes));
      return jsonResponse.map((post) => Post.fromJson(post)).toList();
    } else {
      print('取得貼文失敗: ${response.body}');
      throw Exception('取得貼文失敗: ${response.body}');
    }
  }

  /// 建立新貼文
  Future<Post> createPost(String content) async {
    _checkTokenAndUrl();
    
    print('建立新貼文');
    final response = await http.post(
      Uri.parse('$baseUrl/api/posts'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({'content': content}),
    );
    
    if (response.statusCode == 201) {
      print('貼文建立成功');
      return Post.fromJson(jsonDecode(utf8.decode(response.bodyBytes)));
    } else {
      print('建立貼文失敗: ${response.body}');
      throw Exception('建立貼文失敗: ${response.body}');
    }
  }

  /// 新增評論到貼文
  Future<Comment> addComment(int postId, String content) async {
    _checkTokenAndUrl();
    
    print('新增評論到貼文 $postId');
    final response = await http.post(
      Uri.parse('$baseUrl/api/posts/$postId/comments'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({'content': content}),
    );
    
    if (response.statusCode == 201) {
      print('評論新增成功');
      return Comment.fromJson(jsonDecode(utf8.decode(response.bodyBytes)));
    } else {
      print('新增評論失敗: ${response.body}');
      throw Exception('新增評論失敗: ${response.body}');
    }
  }

  /// 檢查令牌和 URL 是否設置
  void _checkTokenAndUrl() {
    if (baseUrl.isEmpty) {
      throw Exception('伺服器 URL 未設置');
    }
    if (token == null) {
      throw Exception('未登入，令牌不存在');
    }
  }
}